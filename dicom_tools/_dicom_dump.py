import logging
import pydicom as dicom
from pathlib import Path

from ._utils import ensure_out_dir

LOGGER_ID = "dicom"
_logger = logging.getLogger(LOGGER_ID)


# Run static type checking with the following command:
# mypy _dicom_dump.py --ignore-missing-imports --allow-redefinition
from typing import Any, Dict, Optional, Callable, TextIO, TypeVar, Type
PathLike = TypeVar("PathLike", str, Path)
DatasetDict = Dict[str, Dict[str, Any]]
DatasetType = Type[dicom.Dataset]
ReaderCallable = Callable[[TextIO], DatasetDict]
WriterCallable = Callable[[PathLike, TextIO], None]

def _tag_to_str(tag: dicom.tag.TagType) -> str:
    tag = dicom.tag.Tag(tag)
    return "0x%04x%04x" % (tag.group, tag.elem)


def _flatten_list(value: Any) -> Any:
    if (isinstance(value, list) and len(value)==1 and
        not isinstance(value[0], list)):
        return value[0]
    else:
        return value


def _json_dict_to_readable(dct: DatasetDict,
                           skip_binary: bool=False,
                           skip_nonstd: bool=False) -> DatasetDict:
    ret = {}
    for tag, elm in dct.items():
        vr = elm["vr"]
        keyword = dicom.datadict.keyword_for_tag(tag)
        if not keyword and skip_nonstd:
            continue
        tag = "0x%s" % tag
        data = dict()
        #if keyword:
        #    data["keyword"] = keyword
        data["tag"] = tag
        data["vr"] = vr
        if "Value" in elm:
            if vr == "SQ":
                # Recursion for sequences
                value = [_json_dict_to_readable(v) for v in elm["Value"]]
            else:
                value = _flatten_list(elm["Value"])
            data["value"] = value
        if "InlineBinary" in elm and not skip_binary:
            data["binary"] = elm["InlineBinary"]
        if "BulkDataURI" in elm:
            data["uri"] = elm["BulkDataURI"]
        name = keyword if keyword else tag
        ret[name] = data
    return ret


def _readable_to_json_dict(dct: DatasetDict,
                           skip_binary: bool=False,
                           skip_nonstd: bool=False) -> DatasetDict:
    ret = {}
    for key, elm in dct.items():
        data = {}
        if skip_nonstd:
            try:
                dicom.tag.Tag(key)
            except KeyError:
                continue
        if "vr" in elm:
            data["vr"] = elm["vr"]
        if "value" in elm:
            value = elm["value"]
            if "vr" in data and data["vr"] == "SQ":
                # Recursion for sequences
                value = [_readable_to_json_dict(v) for v in value]
            elif not isinstance(value, list):
                value = [value]
            data["Value"] = value
        if "binary" in elm and not skip_binary:
            data["InlineBinary"] = elm["binary"]
        if "uri" in elm:
            data["BulkDataURI"] = elm["uri"]
        ret[key] = data
    return ret


def _to_dump_dict(ds: DatasetType,
                  skip_binary: bool=False,
                  skip_nonstd: bool=False) -> Dict:
    dct = {}
    dct["info"] = ("This file was created by package dicom_tools. It can be "
                   "read as a DICOM dataset using from_yaml() or from_json(). "
                   "An element can be addressed using its keyword string or "
                   "hexadecimal representation. Example: the element "
                   "(0008, 0060) can be addressed by Modality or 0x00080060. "
                   "The only required element field is 'vr' (value "
                   "representation). Other relevant fields are 'value', "
                   "'binary' or 'uri', but they are optional. If not provided,"
                   "the value is set to None.")
    dct["file_meta"] = _json_dict_to_readable(dct=ds.file_meta.to_json_dict(),
                                              skip_binary=False,
                                              skip_nonstd=True)
    dct["data"] = _json_dict_to_readable(dct=ds.to_json_dict(),
                                         skip_binary=skip_binary,
                                         skip_nonstd=skip_nonstd)
    return dct


def _from_dump_dict(dct: DatasetDict,
                    skip_binary: bool=False,
                    skip_nonstd: bool=False) -> DatasetType:
    empty_dict: DatasetDict = {}  # Required for mypy
    dct_data = _readable_to_json_dict(dct.get("data", empty_dict.copy()),
                                      skip_binary=skip_binary,
                                      skip_nonstd=skip_nonstd)
    ds = dicom.dataset.Dataset.from_json(dct_data)
    dct_meta = _readable_to_json_dict(dct.get("file_meta", empty_dict.copy()),
                                      skip_binary=False,
                                      skip_nonstd=True)
    ds.file_meta = dicom.dataset.FileMetaDataset.from_json(dct_meta)
    return ds


def _dump_to_file(path: PathLike,
                  data: DatasetType,
                  writer: WriterCallable,
                  suffix: str,
                  skip_binary: bool=False,
                  skip_nonstd: bool=False) -> bool:
    path = Path(path)
    if path.suffix.lower() != suffix:
        msg = "No file is written. Path should have %s suffix: %s"
        _logger.error(msg, suffix, path)
        return False
    ensure_out_dir(path.parent)
    with open(path, "w") as fid:
        dct = _to_dump_dict(ds=data,
                            skip_binary=skip_binary,
                            skip_nonstd=skip_nonstd)
        writer(dct, fid)
    return path.is_file()


def _load_from_file(path: PathLike,
                    reader: ReaderCallable,
                    skip_binary: bool=False,
                    skip_nonstd: bool=False) -> DatasetType:
    path = Path(path)
    if not path.is_file():
        msg = "File does not exist: %s" % path
        raise FileNotFoundError(msg)

    with open(path, "r") as fid:
        dct = reader(fid)
        ds = _from_dump_dict(dct=dct,
                             skip_binary=skip_binary,
                             skip_nonstd=skip_nonstd)
    return ds


def dump_to_json(path: PathLike,
                 data: DatasetType,
                 skip_binary: bool=False,
                 skip_nonstd: bool=False) -> bool:
    """
    Dump DICOM to JSON file in a readable format.
    """
    import json
    writer = lambda dct, fid: json.dump(dct, fid, indent=4)
    return _dump_to_file(path=path, data=data,
                         writer=writer, suffix=".json",
                         skip_binary=skip_binary,
                         skip_nonstd=skip_nonstd)


def dump_to_yaml(path: PathLike,
                 data: DatasetType,
                 skip_binary: bool=False,
                 skip_nonstd: bool=False) -> bool:
    """
    Dump DICOM to YAML file in a readable format.
    """
    import yaml
    def default_representer(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))
    yaml.representer.SafeRepresenter.add_representer(None, default_representer)
    writer = lambda dct, fid: yaml.safe_dump(dct, fid,
                                             sort_keys=False,
                                             width=60)
    return _dump_to_file(path=path, data=data,
                         writer=writer, suffix=".yaml",
                         skip_binary=skip_binary,
                         skip_nonstd=skip_nonstd)


def from_json(path: PathLike,
              skip_binary: bool=False,
              skip_nonstd: bool=False) -> DatasetType:
    """
    Create DICOM from JSON file.

    Note:
    -----
    The JSON file is expected to have the same format as the one that is
    created by dump_to_json(). The file should consist of two sections
    "data" and "file_meta". Private data is only partially supported.
    """
    import json
    return _load_from_file(path=path,
                           reader=json.load,
                           skip_binary=skip_binary,
                           skip_nonstd=skip_nonstd)


def from_yaml(path: PathLike,
              skip_binary: bool=False,
              skip_nonstd: bool=False) -> DatasetType:
    """
    Create DICOM from YAML file.

    Note:
    -----
    The YAML file is expected to have the same format as the one that is
    created by dump_to_yaml(). The file should consist of two sections
    "data" and "file_meta". Private data is only partially supported.
    """
    import yaml
    return _load_from_file(path=path,
                           reader=yaml.safe_load,
                           skip_binary=skip_binary,
                           skip_nonstd=skip_nonstd)
