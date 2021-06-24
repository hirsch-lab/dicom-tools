#!/usr/bin/env python
import logging
import argparse
from .._dicom_io import copy_from_file
from .._utils import setup_logging


def _run(args):
    setup_logging(verbosity=args.verbosity)
    copy_from_file(in_dir=args.in_dir,
                   out_dir=args.out_dir,
                   list_file=args.list_file,
                   list_column=args.list_column,
                   flat_copy=args.flat_copy)


def _parse_args():
    description = ("Copy content from source_dir to out_dir as defined "
                   "in the list_file.")
    parser = argparse.ArgumentParser(description=description, add_help=False)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-l", "--list-file", required=True,
                        help="File containing the dicoms to be copied.")
    parser_group.add_argument("-i", "--in-dir", required=True,
                        help="Directory of a dicom source.")
    parser_group.add_argument("-o", "--out-dir", default="./out",
                        help="Desination directory. Default: './out'")
    parser_group.add_argument("--list-column", tpye=str, default=None,
                              help=("Specify a column that contains the file "
                                    "filter data in the list file. If this "
                                    "option is provided, the list file will be "
                                    "parsed as a .csv file WITH header row."))
    parser_group.add_argument("--flat-copy", action="store_true",
                              help="Ignore subfolder hierarchy.")
    parser_group.add_argument("-v", "--verbosity", action="count",
                              help="Increase verbosity.")
    parser_group.add_argument("-h", "--help", action="help",
                        help="Show this help text.")
    parser_group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
