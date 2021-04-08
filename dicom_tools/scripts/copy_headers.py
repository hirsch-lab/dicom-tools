#!/usr/bin/env python
import logging
import argparse
from .._dicom_io import copy_headers
from .._utils import setup_logging


def _run(args):
    root = logging.getLogger()
    setup_logging(verbosity=args.verbosity)
    ret = copy_headers(in_dir=args.in_dir,
                       out_dir=args.out_dir,
                       glob_expr="**/*.dcm",
                       file_filter=None,
                       first_file_only=not args.all,
                       show_progress=True,
                       skip_empty=True)


def _parse_args():
    description = "Copy DICOM files without pixel data."
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-i", "--in_dir", required=True,
                              help="Directory of a dicom source. Required.")
    parser_group.add_argument("-o", "--out_dir", default="./out",
                              help="Desination directory. Default: './out'")
    parser_group.add_argument("-v", "--verbosity", action="count",
                              help="Increase verbosity")
    parser_group.add_argument("-h", "--help", action="help",
                              help="Show this help text")
    parser_group.add_argument("-a", "--all", action="store_true",
                              help=("Create a header for every DICOM instance "
                                    "in a series. By default, the header of "
                                    "only the first instance is copied."))
    parser_group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
