#!/bin/bash
tsv_file="$1"
while IFS=$'\t' read -r input_wav output_mp3 start_segment end_segment duration annotation ; do
    clean_annotation=$(echo "$annotation" | sed "s/[|,\"\.?!]//g")
    echo "./mp3/$output_mp3,$clean_annotation"
done < "$tsv_file"
