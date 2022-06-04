import logging
import dicom2nifti as dcm2nii
import nibabel as nib
import numpy as np
import pydicom as dicom
import tempfile
import PIL as pil

from pathlib import Path
from ._utils import (search_files, create_progress_bar, ensure_out_dir)
from ._dicom_io import move_file_or_folder

_LOGGER_ID = "dicom"
_logger = logging.getLogger(_LOGGER_ID)


# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import Type, TypeVar, Tuple, List, Optional, Any, Iterator
import numpy.typing as npt
PathLike = TypeVar("PathLike", str, Path)

ImageType = Type[pil.Image.Image]

def _format_image(img: ImageType) -> npt.NDArray:
    # Turn multi-channel images into gray-scale.
    # Supported only for 8bit images.
    color_modes = ["RGB", "RGBA", "CMYK", "YCbCr",
                   "LAB", "HSV", "RGBX", "RGBa",
                   "BGR;15", "BGR;16", "BGR;24",
                   "BGR;32"]
    if img.mode in color_modes:
        _logger.warning("Caution! Larger than 8-bit multi-channel images \n"
                        "are converted to 8-bit grayscale images\n"
                        "current image dtype:", img.mode)
        img = img.convert("L")

    # TODO: Need to implement pixel-depth conversion?
    # Numpy preserves the depth as read from the image.
    img = np.asarray(img)
    return img


ImageYield = Iterator[Tuple[Optional[npt.NDArray], PathLike, int]]
def _read_image_gen(paths: List[Path],
                    sep: str="_") -> ImageYield:
    """
    The purpose of this generator is to return images, frame by frame.
    Most notably, it also handles multi-frame images. The generator yields
    the (optional) image, the path and the progress in PERCENT!
    """
    n = len(paths)
    for i, path in enumerate(paths):
        progress: int = round(i/n*100)
        if not path.is_file():
            yield None, path, progress
            continue
        try:
            img = pil.Image.open(path)
        except pil.UnidentifiedImageError:
            yield None, path, progress
            continue
        n_frames = getattr(img, "n_frames", 1)
        if n_frames == 1:
            yield _format_image(img), path, progress
        elif n_frames >= 1:
            for j, page in enumerate(pil.ImageSequence.Iterator(img)):
                progress = round((i+j/n_frames)/n*100)
                path = path.parent / (path.stem + sep + str(j) + path.suffix)
                yield _format_image(page), path, progress


def _infer_sopclass_uid(storage_type: Optional[str]=None) -> Optional[str]:
    """
    TODO: needed?
    https://pydicom.github.io/pynetdicom/stable/service_classes/storage_service_class.html
    """
    if storage_type is None:
        sopclass_uid = None
    elif storage_type == "CT":
        sopclass_uid = "1.2.840.10008.5.1.4.1.1.2"
        # sopclass_uid = pynetdicom.sop_class.CTImageStorage
    elif storage_type in ("MRI", "MR"):
        sopclass_uid = "1.2.840.10008.5.1.4.1.1.4"
        #sopclass_uid = pynetdicom.sop_class.MRImageStorage
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
    file_meta.MediaStorageSOPClassUID = _infer_sopclass_uid(storage_type)  # type: ignore
    file_meta.MediaStorageSOPInstanceUID = dicom.uid.generate_uid()
    #file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = dicom.uid.ExplicitVRLittleEndian
    #file_meta.TransferSyntaxUID = dicom.uid.ImplicitVRLittleEndian
    dicom.dataset.validate_file_meta(file_meta, enforce_standard=True)
    return file_meta


def _apply_attributes(data: dicom.Dataset,
                      meta: dicom.dataset.FileMetaDataset,
                      attributes: Optional[dicom.Dataset]) -> None:
    if attributes:
        for elem in attributes:
            data[elem.tag] = elem

        for elem in attributes.file_meta:
            meta[elem.tag] = elem


def _ndarray2dicom(data: np.ndarray,
                   attributes: Optional[dicom.Dataset],
                   instance_number: int,
                   default_series_uid: dicom.uid.UID,
                   default_study_uid: dicom.uid.UID) -> dicom.Dataset:
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
    ds.SeriesInstanceUID = default_series_uid
    ds.StudyInstanceUID = default_study_uid
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
                dtype: Optional[str]=None,
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
    progress = create_progress_bar(size=100,  # Progress in percent
                                   label="WORK",
                                   enabled=show_progress)
    progress.start()

    # Series and study UIDs can be overridden via the attributes.
    # However, to make sure that the images of the same stack belong to
    # the same series, we have to set the same identifier to all frames.
    series_uid = dicom.uid.generate_uid()
    study_uid = dicom.uid.generate_uid()

    for i, (img, path, prog) in enumerate(_read_image_gen(paths)):
        if img is None:
            _logger.error("Skipping invalid image:", path)
            continue
        ds = _ndarray2dicom(data=img,
                            attributes=attributes,
                            instance_number=i+1,
                            default_series_uid=series_uid,
                            default_study_uid=study_uid)
        if dtype is not None:
            ds.astype(dtype)
        ds.save_as(out_dir/(path.stem + ".dcm"))
        progress.update(prog)
    progress.finish()


def dicom2nifti(in_dir: PathLike,
                out_dir: PathLike,
                comp: Optional[bool]=True,
                reor: Optional[bool]=False) -> None:

    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    if not ensure_out_dir(out_dir):
        return None
    with tempfile.TemporaryDirectory() as tmp_dir:
        dcm2nii.convert_directory(in_dir, tmp_dir,
                                  compression=comp,
                                  reorient=reor)
        files = list(Path(tmp_dir).glob("*.nii*"))
        if len(files)==0:
            _logger.error("Conversion to NIfTI failed.")
            return None
        assert len(files) == 1
        ret_path = Path(files[0])
        out_path = out_dir / (in_dir.name + "".join(ret_path.suffixes))
        move_file_or_folder(src=ret_path, dst=out_path)


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
    progress = create_progress_bar(size=len(paths),
                                   label="# NIfTI files",
                                   enabled=show_progress)
    progress.start()
    for i, path in enumerate(paths):
        try:
            nii_file = nib.load(path)
        except:
            _logger.error("Could not load file: %s", path.stem)
            continue

        # Series and study UIDs can be overridden via the attributes.
        # However, to make sure that the images of the same stack belong to
        # the same series, we have to set the same identifier to all frames.
        series_uid = dicom.uid.generate_uid()
        study_uid = dicom.uid.generate_uid()

        nii_array = np.asanyarray(nii_file.dataobj)
        n_slices = nii_array.shape[2]
        for j in range(n_slices):
            # Array transpose to keep orientation
            # check validity of array! PIL image
            ds = _ndarray2dicom(data=nii_array[:,:,j].T,
                                attributes=attributes,
                                instance_number=int(j+1),
                                default_series_uid=series_uid,
                                default_study_uid=study_uid)

            filename = "%s_%d.dcm" % (path.stem.split(".")[0], j)
            ds.save_as(out_dir / filename)
        progress.update(i)
    progress.finish()
