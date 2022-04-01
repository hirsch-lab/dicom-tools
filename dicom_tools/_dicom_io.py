import re
import errno
import shutil
import logging
import pandas as pd
import pydicom as dicom
from pathlib import Path
from itertools import islice
from datetime import datetime
from collections import defaultdict
from ._utils import (check_in_dir,
                     ensure_out_dir,
                     create_progress_bar)


_NA = "N/A"
_DICOM_SUFFIX = ".dcm"
_NO_FILES = [ ".DS_Store", ]
_LOGGER_ID = "dicom"
_DEFAULT_DATE = "20000101"
_logger = logging.getLogger(_LOGGER_ID)

# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import TypeVar, Union, Optional, Tuple, List, Callable, Any
# Protocol is part of the typing module in Python 3.8+,
# but it remains available for older Python versions.
from typing_extensions import Protocol
# TypeVar vs. Union: https://stackoverflow.com/questions/58903906
PathLike = TypeVar("PathLike", str, Path)
#PathLike = Union[str, Path]
OptionalPathList = Optional[List[Path]]
OptionalFilter = Optional[Callable[[PathLike], bool]]
class CallablePrinter(Protocol):
    def __call__(self, msg: Optional[str]=None) -> None: ...
OptionalPrinter = Optional[CallablePrinter]


def copy_from_file(in_dir: PathLike,
                   out_dir: PathLike,
                   list_file: PathLike,
                   list_column: Optional[str]=None,
                   flat_copy: bool=False,
                   raise_if_missing: bool=True,
                   show_progress: bool=True) -> OptionalPathList:
    """
    Copy content from source_dir to out_dir as defined in the list_file.
    """
    list_file = Path(list_file)
    if not list_file.is_file():
        _logger.error("List file does not exist: %s", list_file)
        return None

    if list_column is not None:
        df = pd.read_csv(list_file, comment="#")
        if list_column not in df:
            _logger.error("List file misses a column named '%s'!", list_column)
            return None
        to_copy = df[list_column]
    else:
        df = pd.read_csv(list_file, comment="#", header=None)
        # Pick first column
        to_copy = df.iloc[:,0]
    return copy_from_list(in_dir=in_dir,
                          out_dir=out_dir,
                          to_copy=to_copy,
                          flat_copy=flat_copy,
                          raise_if_missing=raise_if_missing,
                          show_progress=show_progress)


def copy_from_list(in_dir: PathLike,
                   out_dir: PathLike,
                   to_copy: List[str],
                   flat_copy: bool=False,
                   raise_if_missing: bool=True,
                   show_progress: bool=True) -> OptionalPathList:
    """
    Note: This function is generic, it copies all files or folders specified
    in the input list, not just DICOMs.
    """
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    if not check_in_dir(in_dir):
        return None
    if not ensure_out_dir(out_dir):
        return None

    n_files = len(to_copy)
    _logger.info("Copying data...")
    progress = create_progress_bar(size=n_files,
                                   label="WORK",
                                   enabled=show_progress)
    progress.start()

    entries_copied = []
    for i, filename in enumerate(to_copy):
        src = in_dir / filename
        if flat_copy:
            dst = out_dir / Path(filename).name
        else:
            dst = out_dir / filename

        # Copy directory robustly.
        # Source: http://stackoverflow.com/questions/1994488/ (user tzot)
        ensure_out_dir(dst.parent, raise_error=True)
        if not dst.exists():
            _logger.info("Copying content: %s...", filename)
            try:
                shutil.copytree(src, dst)
            except OSError as exc:
                if exc.errno == errno.ENOTDIR:
                    shutil.copy(src, dst)
                else:  # pragma no cover
                    if raise_if_missing:
                        _logger.error("Could not copy content %s.", src)
                        raise
                    else:
                        _logger.warning("Could not copy content %s.", src)
        else:
            _logger.info("Skipping existing content: %s...", filename)

        if dst.exists():
            entries_copied.append(dst)

        progress.update(i)
    progress.finish()
    _logger.info("Done!")
    _logger.info("Copied %d out of %d entries.",
                 len(entries_copied), len(to_copy))

    return entries_copied


def copy_headers(in_dir: PathLike,
                 out_dir: PathLike,
                 glob_expr: str=f"**/*{_DICOM_SUFFIX}",
                 file_filter: OptionalFilter=None,
                 first_file_only: bool=True,
                 show_progress: bool=True,
                 skip_empty: bool=True) -> OptionalPathList:
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    if not check_in_dir(in_dir):
        return None
    if not ensure_out_dir(out_dir):
        return None

    # Identify the files, can be slow
    _logger.info("Collecting DICOM files...")
    dicom_files = sorted(in_dir.glob(glob_expr))
    n_files = len(dicom_files)

    # Apply filter
    if file_filter:
        _logger.info("Filtering files...")
        _logger.info("  - files before filtering: %d", n_files)
        dicom_files = list(filter(file_filter, dicom_files))
        n_files = len(dicom_files)
        _logger.info("  - files after filtering:  %d", n_files)

    # Copy action
    files_created = []
    folders_created = set()

    _logger.info("Copying DICOM files...")
    progress = create_progress_bar(size=n_files,
                                   label="WORK",
                                   threaded=True,
                                   enabled=show_progress)
    previous_parent = None
    for i, filepath in enumerate(dicom_files):
        progress.update(i)
        out_file = out_dir / filepath.relative_to(in_dir)
        out_parent = out_file.parent
        if not ensure_out_dir(out_parent):  # pragma no cover
            continue
        folders_created.add(out_parent)
        if first_file_only and out_parent==previous_parent:
            continue
        dataset : dicom.Dataset = dicom.dcmread(filepath)
        # This fixes a problem for corrupted data sets.
        pixel_data_tag = dicom.tag.Tag("PixelData")
        if not pixel_data_tag in dataset and skip_empty:
            continue
        elif pixel_data_tag in dataset:
            # Reset pixel data.
            del dataset.PixelData
        else:
            _logger.debug("No pixel data to remove: %s", filepath.stem)
        dataset.save_as(str(out_file),
                        write_like_original=True)
        files_created.append(out_file)
        previous_parent = out_parent
    progress.finish()
    _logger.info("Done!")
    _logger.info("Created %d DICOM headers in %d folders.",
                 len(files_created), len(folders_created))
    return files_created


def print_info(path: PathLike,
               printer: OptionalPrinter=None,
               detailed: bool=False) -> None:
    path = Path(path)

    def default_printer(msg:Optional[str]=None) -> None:
        msg = "" if msg is None else msg
        _logger.info(msg)
    printer = default_printer if printer is None else printer

    if path.is_dir():
        files = list(sorted(path.glob(f"*{_DICOM_SUFFIX}")))
        if not files:
            msg = "No DICOM files found under this location: %s"
            _logger.error(msg, path)
            return
        # Pick first entry
        path = files[0]
    if not path.exists():
        _logger.error("File or folder does not exist: %s", path)
        return
    if not path.suffix == _DICOM_SUFFIX:
        _logger.error("Expecting a DICOM file as input: %s", path)
        return

    dataset : dicom.Dataset = dicom.dcmread(path)

    if detailed:
        printer()
        printer("Entire DICOM dictionary:\n" + str(dataset))

    printer()
    printer("Filename.........: %s" % path.name)
    printer("Storage type.....: %s" % dataset.SOPClassUID)
    printer()

    pat_name = dataset.PatientName
    pat_name = _NA if not pat_name else pat_name
    printer("Patient's name...: %s" % pat_name)
    printer("Patient id.......: %s" % dataset.PatientID)
    printer("Modality.........: %s" % dataset.Modality)
    printer("Study date.......: %s" % dataset.StudyDate)

    if "PixelData" in dataset:
        rows = int(dataset.Rows)
        cols = int(dataset.Columns)
        printer("Image size.......: {rows:d} x {cols:d}, {size:d} bytes".format(
                rows=rows, cols=cols, size=len(dataset.PixelData)))
        if "PixelSpacing" in dataset:
            printer("Pixel spacing....: %s" % dataset.PixelSpacing)

    if "NumberOfFrames" in dataset:
       n_frames = int(dataset.NumberOfFrames)
    else:
       dir_path = path if path.is_dir() else path.parent
       n_frames = len(list(dir_path.glob(f"*{_DICOM_SUFFIX}")))
    printer("Number of frames.: %s" % n_frames)
    printer("Slice location...: %s" % dataset.get("SliceLocation", _NA))
    printer("Seq. description.: %s" % dataset.get("SequenceDescription", _NA))


def create_dataset_summary(in_dir: PathLike,
                           glob_expr: Optional[str]=None,
                           reg_expr: Optional[str]=None,
                           n_series_max: Optional[int]=None,
                           show_progress: bool=True,
                           skip_localizers: bool=True) -> pd.DataFrame:
    """
    Recursively search for DICOM data in a folder and represent the data
    as a pandas DataFrame.
    """
    in_dir = Path(in_dir)

    def _safe_read(file_path: Path) -> Optional[dicom.Dataset]:
        dcm = None
        try:
            dcm = dicom.dcmread(file_path)
        except dicom.errors.InvalidDicomError:
            _logger.info("Ignoring file %s", file_path)
        return dcm

    def _canonical_datetime(date: str,
                            time: Optional[str]=None) -> Optional[datetime]:
        # If time contains a ".", it has a sub-second resolution.
        if not date and not time:
            return None
        with_subsecs = time is not None and "." in time
        if not date:
            date = _DEFAULT_DATE
        if not time:
            dt = datetime.strptime(date,"%Y%m%d")
        elif not with_subsecs:
            dt = datetime.strptime(date+time,"%Y%m%d%H%M%S")
        elif with_subsecs:
            dt = datetime.strptime(date+time,"%Y%m%d%H%M%S.%f")
        else:
            assert False
        return dt

    def _extract_time(dataset: dicom.Dataset,
                      dataset_id: str,
                      which: str="Acquisition") -> Optional[datetime]:
        which = which.capitalize()
        date = dataset.get(which+"Date", _DEFAULT_DATE)
        time = dataset.get(which+"Time")
        dt = _canonical_datetime(date=date, time=time)
        return dt

    def _extract_key(dataset: dicom.Dataset,
                     dataset_id: str,
                     key: str,
                     default: Any=_NA,
                     warn: bool=True) -> Any:
        value = dataset.get(key, None)
        if value is None:
            if warn:  # pragma no cover
                _logger.warning("Dataset has no tag '%s': %s",
                                key, dataset_id)
            value = default
        return value


    def _extract_dicom_info(dcm, parent_dir, skip_localizers):
        if dcm is None:
            return

        sid         = str(parent_dir)
        patient_id  = dcm.PatientID
        dt_study    = _extract_time(dcm, sid, which="Study")
        dt_series   = _extract_time(dcm, sid, which="Series")
        dt_acq      = _extract_time(dcm, sid, which="Acquisition")
        modality    = _extract_key(dcm, sid, "Modality",          _NA,  True)
        image_type  = _extract_key(dcm, sid, "ImageType",         _NA,  True)
        sop_uid     = _extract_key(dcm, sid, "SOPInstanceUID",    _NA,  True)
        study_uid   = _extract_key(dcm, sid, "StudyInstanceUID",  _NA,  True)
        series_uid  = _extract_key(dcm, sid, "SeriesInstanceUID", _NA,  True)
        cols        = _extract_key(dcm, sid, "Columns",           None, True)
        rows        = _extract_key(dcm, sid, "Rows",              None, True)
        size        = _NA if (cols==None or rows==None) else [cols, rows]
        spacing     = _extract_key(dcm, sid, "PixelSpacing",      _NA,  False)
        n_frames    = _extract_key(dcm, sid, "NumberOfFrames",    None, False)
        description = _extract_key(dcm, sid, "SeriesDescription", _NA,  False)

        # Extract image type
        # https://dicom.innolitics.com/ciods/ct-image/general-image/00080008
        pixel_data_tag = image_type[0]
        patient_exam_tag = image_type[1]
        info_object_def_tag = image_type[2] if len(image_type) >= 3 else _NA
        implementation_tag = image_type[3:]

        if n_frames is None:
            n_frames = len(dicom_files)

        if skip_localizers and modality.lower() in ("ct", "mr"):
            if info_object_def_tag.lower() == "localizer":
                # We happened to pick a localizer image, that is not
                # really representative for the scan (it's single frame).
                # http://www.otpedia.com/entryDetails.cfm?id=398
                # Localizer images, also called scout images, are used in
                # MR and CT studies to identify the relative anatomical
                # position of a collection of cross-sectional images.
                _logger.debug("Skipping localizer for %s", parent_dir)
                return

        # Clean dirty strings
        description = description.replace('\"',"")
        description = description.replace("\n","_")
        description = description.replace(";","_")

        # This forms the row of the resulting table
        row = dict(patientId=patient_id,
                   caseId=None,
                   seriesDateTime=dt_series,
                   studyDateTime=dt_study,
                   acquisitionDateTime=dt_acq,
                   modality=modality,
                   pixelTag=pixel_data_tag,
                   examTag=patient_exam_tag,
                   imageTags= image_type,
                   size=size,
                   spacing=spacing,
                   nFrames=n_frames,
                   studyInstanceUID=study_uid,
                   seriesInstanceUID=series_uid,
                   sopInstanceUID=sop_uid,
                   seriesDescription=description,
                   path=parent_dir)
        return row


    if not in_dir.is_dir():
        _logger.error("Input folder does not exist: %s", in_dir)
        exit(-1)

    # Choose files.
    # - if neither glob_expr nor reg_expr is provided: search all .dcm files
    # - if only glob_expr is provided:                 filter by glob_expr
    # - if only reg_expr is provided:                  filter by reg_expr
    # - if both glob_expr and reg_expr are provided:   glob_expr, then reg_expr
    files_iter = None
    if glob_expr is None and reg_expr is None:
        glob_expr = f"**/*{_DICOM_SUFFIX}"
    if glob_expr:
        files_iter = in_dir.glob(glob_expr)
    else:
        files_iter = in_dir.rglob("*")
    if reg_expr:
        pattern = re.compile(reg_expr)
        files_iter = (f for f in files_iter if pattern.match(str(f)))
    files: List[Path] = sorted(f for f in files_iter
                               if (f.is_file() and
                                   f.name not in _NO_FILES))

    if len(files)==0:
        _logger.error("No files found in directory: %s", in_dir)
        _logger.error("Glob expression: %s", glob_expr)
        _logger.error("Regular expression: %s", reg_expr)
        return

    # Construct a dict that maps the series to the *first* DICOM file.
    # Assumption: DICOM series are located in distinct folders that
    # contain the files/DICOM instances.
    files_per_series = defaultdict(list)
    for f in files:
        parent = f.parent
        files_per_series[parent].append(f)
    if n_series_max and n_series_max > 0:
        # Take first n items.
        new_dict = dict(islice(files_per_series.items(),
                               n_series_max))
        files_per_series = defaultdict(list)
        files_per_series.update(new_dict)

    # Number of files = number of DICOM instances.
    # A DICOM instance can be a single slice or stack of slices.
    # n_files = len(files)
    n_files = sum(map(len, files_per_series.values()))
    n_series = len(files_per_series)

    _logger.info("Collecting data...")
    progress = create_progress_bar(size=n_series,
                                   label="WORK",
                                   threaded=True,
                                   enabled=show_progress)
    progress.start()
    data = []
    for i, (parent_dir, dicom_files) in enumerate(files_per_series.items()):
        # Use the first valid file from which to extract data.
        # len(files)>0 is guaranteed.
        for file_path in dicom_files:
            dcm = _safe_read(file_path)
            if dcm is None:
                continue  # Inner loop
            row = _extract_dicom_info(dcm=dcm, parent_dir=parent_dir,
                                      skip_localizers=skip_localizers)
            if row is not None:
                # We have found a valid "first" DICOM of a series.
                break  # Outer loop
        else:
            msg = "Could not read any valid dicom information for folder: %s"
            _logger.warning(msg, parent_dir)
            continue        # Outer loop

        data.append(row)
        progress.update(i)

    progress.finish()

    data = pd.DataFrame(data)
    if not data.empty:
        sort_list = ["patientId", "seriesDateTime"]
        data = data.sort_values(sort_list)
        data = data.reset_index(drop=True)
        data["caseId"] = data.groupby("patientId").cumcount()+1
    _logger.info("Done!")
    return data
