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
_LOGGER_ID = "dicom"
_logger = logging.getLogger(_LOGGER_ID)

# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import TypeVar, Optional, Tuple, List, Callable, Any
# Protocol is part of the typing module in Python 3.8+,
# but it remains available for older Python versions.
from typing_extensions import Protocol
PathLike = TypeVar("PathLike", str, Path)
OptionalPathList = Optional[List[Path]]
OptionalFilter = Optional[Callable[[PathLike], bool]]
class CallablePrinter(Protocol):
    def __call__(self, msg: Optional[str]=None) -> None: ...
OptionalPrinter = Optional[CallablePrinter]


def copy_from_file(in_dir: PathLike,
                   out_dir: PathLike,
                   list_file: PathLike,
                   raise_if_missing: bool=True,
                   show_progress: bool=True) -> OptionalPathList:
    """
    Copy content from source_dir to out_dir as defined in the list_file.
    """
    list_file = Path(list_file)
    if not list_file.is_file():
        _logger.error("List file does not exist: %s", list_file)
        return None

    df = pd.read_csv(list_file, comment="#")
    # Pick first column
    to_copy = df.iloc[:,0]
    return copy_from_list(in_dir=in_dir,
                          out_dir=out_dir,
                          to_copy=to_copy,
                          raise_if_missing=raise_if_missing,
                          show_progress=show_progress)


def copy_from_list(in_dir: PathLike,
                   out_dir: PathLike,
                   to_copy: List[str],
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
        dst = out_dir / filename

        # Copy directory robustly.
        # Source: http://stackoverflow.com/questions/1994488/ (user tzot)
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
        dataset = dicom.read_file(filepath)
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

    dataset = dicom.read_file(path)

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
                           glob_expr: str=f"**/*{_DICOM_SUFFIX}",
                           n_series_max: Optional[int]=None,
                           show_progress: bool=True) -> pd.DataFrame:
    """
    Recursively search for DICOM data in a folder and represent the data
    as a pandas DataFrame.
    """
    in_dir = Path(in_dir)

    def _canonical_datetime(date: str, time:str) -> datetime:
        if len(time.split(".")) > 1:
            dt = datetime.strptime(date+time,"%Y%m%d%H%M%S.%f")
        else:
            dt = datetime.strptime(date+time,"%Y%m%d%H%M%S")
        return dt

    def _extract_time(dataset: dicom.Dataset,
                      dataset_id: str) -> Tuple[datetime, str]:
        if "AcquisitionDate" in dataset and "AcquisitionTime" in dataset:
            dt = _canonical_datetime(date=dataset.AcquisitionDate,
                                     time=dataset.AcquisitionTime)
            dt_type = "AcquisitionDateTime"
        elif "StudyDate" in dataset and "StudyTime" in dataset:
            dt = _canonical_datetime(date=dataset.StudyDate,
                                     time=dataset.StudyTime)
            dt_type = "StudyDateTime"
        elif "InstanceCreationDate" in dataset and "InstanceCreationTime" in dataset:
            dt = _canonical_datetime(date=dataset.InstanceCreationDate,
                                     time=dataset.InstanceCreationTime)
            dt_type = "InstanceCreationDateTime"
        elif "SeriesDate" in dataset and "SeriesTime" in dataset:
            dt = _canonical_datetime(date=dataset.SeriesDate,
                                     time=dataset.SeriesTime)
            dt_type = "SeriesDateTime"
        else:
            _logger.warning("No date tag for dataset: %s", dataset_id)
            dt = datetime.utcfromtimestamp(0)
            dt_type = _NA
        return dt, dt_type

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

    # Construct a dict that maps the series to the *first* DICOM file.
    # Assumption: DICOM series are located in distinct folders that
    # contain the files/DICOM instances.
    files = list(sorted(in_dir.glob(glob_expr)))
    files_per_series = defaultdict(list)
    for f in files:
        series_id = f.parent.name
        files_per_series[series_id].append(f)
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
    for i, (series_id, dicom_files) in enumerate(files_per_series.items()):
        # Always use the first file to extract data from.
        # len(files)>0 is guaranteed.
        file_path   = dicom_files[0]
        series_dir  = file_path.parent
        assert(series_dir.name == series_id)

        sid         = series_id
        dcm         = dicom.read_file(file_path)
        patient_id  = dcm.PatientID
        dt, dt_type = _extract_time(dcm, sid)
        modality    = _extract_key(dcm, sid, "Modality",          _NA,  True)
        sop_uid     = _extract_key(dcm, sid, "SOPInstanceUID",    _NA,  True)
        study_uid   = _extract_key(dcm, sid, "StudyInstanceUID",  _NA,  True)
        series_uid  = _extract_key(dcm, sid, "SeriesInstanceUID", _NA,  True)
        cols        = _extract_key(dcm, sid, "Columns",           None, True)
        rows        = _extract_key(dcm, sid, "Rows",              None, True)
        size        = _NA if (cols==None or rows==None) else [cols, rows]
        spacing     = _extract_key(dcm, sid, "PixelSpacing",      _NA,  False)
        n_frames    = _extract_key(dcm, sid, "NumberOfFrames",    None, False)
        description = _extract_key(dcm, sid, "SeriesDescription", _NA,  False)

        if n_frames is None:
            n_frames = len(dicom_files)

        # Clean dirty strings
        description = description.replace('\"',"")
        description = description.replace("\n","_")
        description = description.replace(";","_")

        # This forms the row of the resulting table
        row = dict(patientId=patient_id,
                   caseId=None,
                   datetime=dt,
                   datetimeType=dt_type,
                   modality=modality,
                   size=size,
                   spacing=spacing,
                   nFrames=n_frames,
                   studyInstanceUID=study_uid,
                   seriesInstanceUID=series_uid,
                   sopInstanceUID=sop_uid,
                   seriesDescription=description,
                   path=series_dir)
        data.append(row)
        progress.update(i)

    data = pd.DataFrame(data)
    data = data.sort_values(["patientId", "datetime"]).reset_index(drop=True)
    data["caseId"] = data.groupby("patientId").cumcount()+1
    progress.finish()
    _logger.info("Done!")
    return data
