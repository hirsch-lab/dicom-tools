import logging
import cv2 as cv
import numpy as np
import pydicom as dicom

#import nibabel as nib

from pathlib import Path

from ._utils import (search_files, create_progress_bar, ensure_out_dir)

_LOGGER_ID = "dicom"
_logger = logging.getLogger(_LOGGER_ID)

# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import TypeVar, Optional, Any
PathLike = TypeVar("PathLike", str, Path)


def _read_image(path: PathLike) -> Optional[np.ndarray]:
    path = Path(path)
    if not path.is_file():
        _logger.error("File does not exist: %s", path)
        return None
    img = cv.imread(str(path), flags=cv.IMREAD_GRAYSCALE)
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
        sopclass_uid = dicom._storage_sopclass_uids.CTImageStorage
    elif storage_type in ("MRI", "MR"):
        # sopclass_uid = "1.2.840.10008.5.1.4.1.1.4"
        sopclass_uid = dicom._storage_sopclass_uids.MRImageStorage
    elif (storage_type in dicom.uid.UID_dictionary and
          dicom.uid.UID_dictionary[storage_type][1] == "SOP Class"):
        sopclass_uid = storage_type
    elif hasattr(dicom._storage_sopclass_uids, storage_type):
        sopclass_uid = getattr(dicom._storage_sopclass_uids, storage_type)
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
                      attributes: Optional[dicom.Dataset]) -> None:
    for elem in attributes:
        data[elem.tag] = elem


def _ndarray2dicom(data: np.ndarray,
                   attributes: Optional[dicom.Dataset],
                   instance_number: int=1) -> dicom.Dataset:
    """
    This method is inspired by inputs from here:
    https://stackoverflow.com/questions/14350675
    """
    modality = None
    storage_type = None
    if attributes and "Modality" in attributes:
        modality = attributes.Modality
        storage_type = modality

    ds = dicom.Dataset()
    ds.file_meta = _default_meta(storage_type=storage_type)

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

    ds.BitsStored = data.itemsize*8
    ds.BitsAllocated = data.itemsize*8
    ds.SamplesPerPixel = 1
    ds.HighBit = 15

    ds.ImagesInAcquisition = "1"

    ds.Rows = data.shape[0]
    ds.Columns = data.shape[1]
    ds.InstanceNumber = instance_number

    # The data! ################################################# fix data.tobytes()!
    ds.PixelData = data.tobytes()

    # ds.ImagePositionPatient = r"0\0\1"
    # ds.ImageOrientationPatient = r"1\0\0\0\-1\0"
    # ds.ImageType = r"ORIGINAL\PRIMARY\AXIAL"

    # ds.RescaleIntercept = 0
    # ds.RescaleSlope = 1
    # ds.PixelSpacing = r"1\1"
    # ds.PhotometricInterpretation = "MONOCHROME2"
    # ds.PixelRepresentation = 1

    if attributes:
        _apply_attributes(data=ds,
                          attributes=attributes)
    dicom.dataset.validate_file_meta(ds.file_meta, enforce_standard=True)
    return ds


def stack2dicom(in_dir: PathLike,
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
    progress = create_progress_bar(size=len(paths),
                                   label="WORK",
                                   enabled=show_progress)
    progress.start()
    for i, path in enumerate(paths):
        img = _read_image(path=path)
        if img is None:
            _logger.error("Skipping image %d...", i)
            continue
        # nifti = nib.Nifti1Image(img, affine=np.eye(4))
        # nib.save(nifti, out_dir/(path.stem + ".nii"))
        ds = _ndarray2dicom(data=img,
                            attributes=attributes,
                            instance_number=i)
        ds.save_as(out_dir/(path.stem + ".dcm"))
        progress.update(i)
    progress.finish()


