import logging
import dicom2nifti
import nibabel as nib
import numpy as np
import pydicom as dicom
import pynetdicom
import tempfile

from PIL import Image
from pathlib import Path
from ._utils import (search_files, create_progress_bar, ensure_out_dir, resolve_multiframe)

_LOGGER_ID = "dicom"
_logger = logging.getLogger(_LOGGER_ID)


# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import TypeVar, Optional, Any
PathLike = TypeVar("PathLike", str, Path)


def _read_image(path: PathLike,
                depth: Optional[str]=None) -> Optional[np.ndarray]:
    path = Path(path)
    if not path.is_file():
        _logger.error("File does not exist: %s", path)
        return None

    img = Image.open(str(path))
    # Turn multi-channel images into grayscale (only able to make 8bit images)
    c_list = ["RGB", "RGBA", "CMYK", "YCbCr",
              "LAB", "HSV", "RGBX", "RGBa",
              "BGR;15", "BGR;16", "BGR;24",
              "BGR;32"]
    if img.mode in c_list:
        _logger.info("Caution! Larger than 8-bit multi-channel images \n"
                     "are converted to 8-bit grayscale images\n"
                     "current image dtype: {}".format(img.mode))
        img = img.convert('L')
    img.load()

    # Need to implement pixel-depth conversion?
    # Numpy is able to read pixel-depth loaded by PIL and therefore
    # switches to right dtype by default. However only up to 16Bit Images
    # have been tested with PIL.

    sup_depth = ["L","P", "I", "F", "LA", "PA",
                 "La", "I;16", "I;16L", "I;16B",
                 "I;16N"]
    assert img.mode in sup_depth, ("The current pixel-depth is not recognised\n"
                                  "by PIL")
    img = np.asarray(img, dtype=depth)
    if img is None:
        _logger.error("Cannot read image: %s", path)
        return None
    return img


def _infer_sopclass_uid(storage_type: Optional[str]=None) -> Optional[str]:
    """
    TODO: Needed?
    """
    if storage_type is None:
        sopclass_uid = None
    elif storage_type == "CT":
        # sopclass_uid = "1.2.840.10008.5.1.4.1.1.2"
        # sopclass_uid = dicom._storage_sopclass_uids.CTImageStorage
        sopclass_uid = pynetdicom.sop_class.CTImageStorage
    elif storage_type in ("MRI", "MR"):
        # sopclass_uid = "1.2.840.10008.5.1.4.1.1.4"
        # sopclass_uid = dicom._storage_sopclass_uids.MRImageStorage
        sopclass_uid = pynetdicom.sop_class.MRImageStorage
    elif (storage_type in dicom.uid.UID_dictionary and
          dicom.uid.UID_dictionary[storage_type][1] == "SOP Class"):
        sopclass_uid = storage_type
    # elif hasattr(dicom._storage_sopclass_uids, storage_type):
    #     sopclass_uid = getattr(dicom._storage_sopclass_uids, storage_type)
    else:
        msg = "This storage SOP class is not supported: %s"
        assert False, msg % storage_type
    return sopclass_uid


def _default_meta(storage_type: Optional[str]=None
                  ) -> dicom.dataset.FileMetaDataset:
    file_meta = dicom.dataset.FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = _infer_sopclass_uid(storage_type)
    file_meta.MediaStorageSOPInstanceUID = dicom.uid.generate_uid()
    #file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = dicom.uid.ExplicitVRLittleEndian
    #file_meta.TransferSyntaxUID = dicom.uid.ImplicitVRLittleEndian
    dicom.dataset.validate_file_meta(file_meta, enforce_standard=True)
    return file_meta


def _apply_attributes(data: dicom.Dataset,
                      meta: dicom.dataset.FileMetaDataset,
                      attributes: Optional[dicom.Dataset]) -> None:
    for elem in attributes:
        data[elem.tag] = elem

    for elem in attributes.file_meta:
        meta[elem.tag] = elem


def _ndarray2dicom(data: np.ndarray,
                   attributes: Optional[dicom.Dataset],
                   instance_number: int=1) -> dicom.Dataset:
    """
    This method is inspired by inputs from here:
    https://stackoverflow.com/questions/14350675
    """
    suffix = ".dcm"
    modality = None
    storage_type = None
    if attributes and "Modality" in attributes:
        modality = attributes.Modality
        storage_type = modality

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix).name
    ds = dicom.dataset.FileDataset(temp_file, {},
                                   file_meta=_default_meta(storage_type=storage_type),
                                   preamble=b"\0" * 128)


    # Default settings. Can be overwritten later.
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.SOPClassUID = _infer_sopclass_uid(storage_type)
    ds.PatientName = "N/A"
    ds.PatientID = "N/A"

    ds.Modality = modality
    ds.SeriesInstanceUID = dicom.uid.generate_uid()
    ds.StudyInstanceUID = dicom.uid.generate_uid()
    ds.FrameOfReferenceUID = dicom.uid.generate_uid()

    ds.PhotometricInterpretation = "MONOCHROME2"

    ds.BitsAllocated = data.itemsize*8
    ds.BitsStored = data.itemsize * 8
    ds.SamplesPerPixel = 1
    ds.HighBit = ds.BitsStored - 1

    ds.Rows = data.shape[0]
    ds.Columns = data.shape[1]
    ds.InstanceNumber = instance_number

    ds.PixelData = data.tobytes()

    # ds.PixelRepresentation = 1 # signed byte (8-bit -> -128 ... 127)
    ds.PixelRepresentation = 0 # unsigned byte (8-bit -> 0 ... 255)

    # ds.ImagesInAcquisition = "1"
    # ds.ImagePositionPatient = r"0\0\1"
    # ds.ImageOrientationPatient = r"1\0\0\0\-1\0"
    # ds.ImageType = r"ORIGINAL\PRIMARY\AXIAL"

    # ds.RescaleIntercept = 0
    # ds.RescaleSlope = 1
    # ds.PixelSpacing = r"1\1"

    if attributes:
        _apply_attributes(data=ds,
                          meta=ds.file_meta,
                          attributes=attributes)
    dicom.dataset.validate_file_meta(ds.file_meta, enforce_standard=True)
    return ds


def stack2dicom(in_dir: PathLike,
                out_dir: PathLike,
                pattern: Optional[str]=None,
                regex: Optional[str]=None,
                n_files: Optional[int]=None,
                pix_depth: Optional[str]=None,
                attributes: Optional[dicom.Dataset]=None,
                show_progress: bool=True) -> None:
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    resolve_multiframe(in_dir=in_dir)
    paths = search_files(in_dir=in_dir,
                         pattern=pattern,
                         regex=regex,
                         n_files=n_files)
    if not ensure_out_dir(out_dir):
        return None
    progress = create_progress_bar(size=len(paths),
                                   label="WORK",
                                   enabled=show_progress)
    progress.start()
    for i, path in enumerate(paths):
        img = _read_image(path=path, depth=pix_depth)
        if img is None:
            _logger.error("Skipping image %d...", i)
            continue
        ds = _ndarray2dicom(data=img,
                            attributes=attributes,
                            instance_number=i)
        ds.save_as(out_dir/(path.stem + ".dcm"))
        progress.update(i)
    progress.finish()


def dicom_2_nifti(in_dir: PathLike,
                  out_dir: PathLike,
                  comp: Optional[bool]=True,
                  reor: Optional[bool]=False) -> None:

    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    if not ensure_out_dir(out_dir):
        return None
    try:
        dicom2nifti.convert_directory(in_dir, out_dir, compression=comp, reorient=reor)
    except:
        _logger.error('Conversion to Nifti failed DICOM integrity compromised.\n'
                      'Check the --help information of the dicoms_to_nifit function.\n\n')


def nifti2dicom(in_dir: PathLike,
              out_dir: PathLike,
              pattern: Optional[str]=None,
              regex: Optional[str]=None,
              n_files: Optional[int]=None,
              attributes: Optional[dicom.Dataset]=None,
              show_progress: bool=True) -> None:

    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    paths = search_files(in_dir=in_dir,
                         pattern=pattern,
                         regex=regex,
                         n_files=n_files)
    if not ensure_out_dir(out_dir):
        return None
    progress1 = create_progress_bar(size=len(paths),
                                   label="# Nifi files",
                                   enabled=show_progress)
    progress1.start()
    for i, path in enumerate(paths):
        try:
            nii_file = nib.load(path)
        except:
            _logger.error('Nifti file {} could not be loaded.\n'
                          'Default Nifti format: *.nii.gz\n'
                          'If there is no compressed file present\n'
                          'use: *.nii as pattern to call the function.\n\n'.format(path.stem))
            continue
        nii_array = np.asanyarray(nii_file.dataobj)
        number_slices = nii_array.shape[2]
        progress2 = create_progress_bar(size=number_slices,
                                       label="DICOM conversion",
                                       enabled=show_progress)
        progress2.start()
        for s in range(number_slices):
            # array transpose to keep orientation
            # check validity of array! PIL image
            ds = _ndarray2dicom(data=nii_array[:,:,s].T,
                                attributes=attributes,
                                instance_number=int(s+1)
                                )
            ds.save_as(out_dir / (path.stem.rsplit(".")[0] + "_{}_".format(str(s)) + ".dcm"))
            progress2.update(s)
        progress2.finish()
        progress1.update(i)
    progress1.finish()
