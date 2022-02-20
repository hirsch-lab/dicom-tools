import sys
sys.path.append("/Users/sandroroth/Documents/Pycharm/dicom_tool/dicom-tools")

import logging
import argparse
from pathlib import Path

from dicom_tools._utils import setup_logging
from dicom_tools._conversion import dicom_2_nifti

LOGGER_ID = "nifti"
_logger = logging.getLogger(LOGGER_ID)

def _run(args):
    setup_logging(verbosity=args.verbosity + 1)
    dicom_2_nifti(in_dir=args.in_dir, out_dir=args.out_dir)


def _parse_args():
    description = ("Convert a stack of DICOM images into a nifti.\n"
                   "The dicom files however need to hold information about\n"
                   "slice-localization and have to exceed the count of 4.\n"
                   "Furthermore is this function only applicable on 3D data sets.\n\n")
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

    group.add_argument("-f", "--force", action="store_true",
                       help="Force writing of output files.")

    # Nifti (how to change? to make it work?)
    # group = parser.add_argument_gourp("Nifti")
    # group.add_argument("-c", "--compression", default=True, type=bool,
    #                    help=("Compresseion to nii.gz. Default: True"))
    # group.add_argument("-r", "--reorient", default=True, type=bool,
    #                    help=("Reorientation of dicom data to LAS orientation. Default: True"))


    group.set_defaults(func=_run)
    return parser.parse_args()



def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()