#!/usr/bin/env python
import ast
import logging
import argparse
import pydicom as dicom
from pathlib import Path

from dicom_tools._utils import (setup_logging,
                                ensure_out_dir)
from dicom_tools._conversion import stack2dicom
from dicom_tools._dicom_dump import dump_to_yaml, from_yaml


LOGGER_ID = "dicom"
_logger = logging.getLogger(LOGGER_ID)

def _dicom_attributes(ds, attributes):
    for key, value in attributes:
        try:
            tag = ast.literal_eval(key)
        except ValueError:
            tag = key
        ds.add_new(tag, dicom.datadict.dictionary_VR(tag), value)


def _create_template_attribute_file(path, force=False):
    path = Path(path)
    if path.is_file() and not force:
        _logger.error("Attribute file already exists: %s", path)
        exit(1)

    ensure_out_dir(path.parent)
    ds = dicom.dataset.Dataset()
    ds.file_meta = dicom.dataset.FileMetaDataset()
    # File meta elements
    ds.file_meta.TransferSyntaxUID = "Explicit VR Little Endian"

    # Standard elements
    ds.Modality = "MR"

    # Dump file
    ret = dump_to_yaml(path=path, data=ds)
    if ret:
        _logger.info("File written: %s", path)


def _run(args):
    setup_logging(verbosity=args.verbosity+1)

    if args.create_attribute_file:
        _create_template_attribute_file(path=args.create_attribute_file,
                                        force=args.force)
        exit(0)

    if args.attribute_file:
        ds = from_yaml(args.attribute_file)
    else:
        ds = dicom.dataset.Dataset()
        ds.file_meta = dicom.dataset.FileMetaDataset()
    _dicom_attributes(ds, args.attribute)
    _dicom_attributes(ds.file_meta, args.meta_attribute)

    stack2dicom(in_dir=args.in_dir,
                out_dir=args.out_dir,
                pattern=args.pattern,
                regex=args.regex,
                n_files=None)


def _parse_args():
    description = ("Convert a stack of images into a multi-file DICOM.\n"
                   "Any image format supported by OpenCV (cv2) can be.\n"
                   "processed. Potential multi-frame images are split\n"
                   "into singles and processed normally.\n\n"
                   "It is possible to augment the DICOM files by additional\n"
                   "data elements. For instance, one can use either\n"
                   "    --attribute KEY VALUE\n"
                   "    --meta-attribute KEY VALUE\n"
                   "to specify attributes common to all frames. More\n"
                   "conveniently, one can load those attributes from a\n"
                   "specification file, see\n"
                   "    --attribute-file PATH\n"
                   "    --create-attribute-file PATH")
    formatter = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)

    # General
    group = parser.add_argument_group("General")
    group.add_argument("-h", "--help", action="help",
                       help="Show this help text")
    group.add_argument("-v", "--verbosity", action="count", default=0,
                       help="Increase verbosity")

    # IO
    group = parser.add_argument_group("IO")
    group.add_argument("-i", "--in-dir", required=True,
                       help=("A folder containing the images."))
    group.add_argument("-o", "--out-dir", default="./out", type=str,
                       help=("Output directory. Default: ./out"))
    group.add_argument("-p", "--pattern", type=str, default="*.*",
                       help=("Glob-pattern to filter the files in the\n"
                             "input directory. Default: '*.*'"))
    group.add_argument("--regex", type=str, default=None,
                       help=("Regular expression pattern to filter the\n"
                             "files in the input directory. Overrides\n"
                             "the glob expression --pattern."))
    group.add_argument("-f", "--force", action="store_true",
                       help="Force writing of output files.")

    # DICOM
    group = parser.add_argument_group("DICOM")
    group.add_argument("--attribute-file", type=str, default=None,
                       help=("Path to a YAML file specifying keys and\n"
                             "values of DICOM attributes. Use argument\n"
                             "--create-attribute-file to create a sample\n"
                             "attribute file."))
    group.add_argument("--create-attribute-file", default=None, type=str,
                       nargs="?", const="./out/sample-attributes.yaml",
                       help=("Create a sample attribute file. By default,\n"
                             "a file sample-attributes.yaml is created in\n"
                             "the output directory."))
    group.add_argument("--attribute", nargs=2, action="append",
                       metavar=("TAGKEY", "VALUE"), default=[],
                       help=("Set DICOM attributes. First argument is\n"
                             "either the tag or key of the attribute,\n"
                             "the second one contains its value.\n"
                             "Examples:\n"
                             "   --attribute '(0x0008,0x0060)' 'MR'\n"
                             "   --attribute '0x00080060' 'MR'\n"
                             "   --attribute '00080060' 'MR'\n"
                             "   --attribute 'Modality' 'MR'"))
    group.add_argument("--meta-attribute", nargs=2, action="append",
                       metavar=("TAGKEY", "VALUE"), default=[],
                       help=("Set file meta information. The first\n"
                             "argument is either the tag or key\n"
                             "of the attribute, while the second one\n"
                             "contains its value. Example:\n"
                             "   --meta-attribute '(0002,0010)' ..."))
    group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
