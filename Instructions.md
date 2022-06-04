# Instructions to use dicom-tool
In the following, all possible functions of the tool are listed and their use is described in more detail.
The corresponding lines of code for the execution of the respective application are given.
Striclty running from the parent folder **``dicom-tools``**.

## stack2dicom
This Application is able to convert different kind of images into the dicom format.
The currently tested image formats are: png / jpg / tiff and multiframe-tiff.

```bash
# Converting to default output folder (dicom-tools/out)
python dicom_tools/scripts/stack_to_dicom.py -i /path/to/images

# Converting to specific folder
python dicom_tools/scripts/stack_to_dicom.py -i /path/to/images -o /path/to/output/folder

# Adding meta-argument
python dicom_tools/scripts/stack_to_dicom.py -i /path/to/images --attribute '(0x0008,0x0060)' 'MR'
python dicom_tools/scripts/stack_to_dicom.py -i /path/to/images --attribute 'Modality' 'MR'

# Use Yaml attribute file for dicom header information
python dicom_tools/scripts/stack_to_dicom.py -i /path/to/images --attribute-file /path/to/yaml/file
```


## dicom2nifti
Conversion of a folder containing multiple dicom files representing a 3D image.
If random files are present in the folder the conversion fails. The function is
also able to save header information from existing dicom files.

```bash
# Creating yaml file from dicom header (no conversion to nifti) save default: /out/current_dicom_attributes.yaml
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder --create-attribute-file
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder --create-attribute-file /output/path/and/name.yaml

# Converting to default output folder (dicom-tools/out)
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder

# Converting to specific folder
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder -o /path/to/output/folder

# Converting without compression
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder --compression False

# Converting with reorientation to LAS orientation
python dicom_tools/scripts/dicoms_to_nifti.py -i /path/to/dicom/folder --reorient True
```

## nifti2dicom
Converting a 3D nifi file back to 2D dicom slices. Handling compressend and
uncompressed images. This function holds the same flags as the stack2dicom
conversion function.

```bash
# Converting to default output folder(dicom-tools/out)
python dicom_tools/scripts/nifti_to_dicoms.py -i /path/to/nifti/folder

# Converting to specific folder
python dicom_tools/scripts/nifti_to_dicoms.py -i /path/to/nifti/folder -o /path/to/output/folder
```

