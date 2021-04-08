#!/usr/bin/env python
import logging
import argparse
from .._dicom_io import copy_from_file
from .._utils import setup_logging


def _run(args):
    setup_logging(verbosity=args.verbosity)
    copy_from_file(in_dir=args.in_dir,
                   out_dir=args.out_dir,
                   list_file=args.list_file)


def _parse_args():
    description = ("Copy content from source_dir to out_dir as defined "
                   "in the list_file.")
    parser = argparse.ArgumentParser(description=description, add_help=False)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-l", "--list_file", required=True,
                        help="File containing the dicoms to be copied.")
    parser_group.add_argument("-i", "--in_dir", required=True,
                        help="Directory of a dicom source. Required.")
    parser_group.add_argument("-o", "--out_dir", default="./out",
                        help="Desination directory. Default: './out'")
    parser_group.add_argument("-v", "--verbosity", action="count",
                              help="Increase verbosity")
    parser_group.add_argument("-h", "--help", action="help",
                        help="Show this help text")
    parser_group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
