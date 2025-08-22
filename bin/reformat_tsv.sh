#!/bin/bash
tsv_file="$1"
while IFS=$'\t' read -r input_wav output_mp3 start_segment end_segment duration txt_len annotation ; do
    clean_annotation=$(echo "$annotation" | sed "s/[|\"]//g")
    output_mp3=${output_mp3// /_}
    echo "./mp3/$output_mp3,$clean_annotation,$duration,$txt_len"
done < "$tsv_file"
