#!/bin/bash

python train.py \
    --dataset cora \
    --attack meta \
    --ptb_rate 0.05 \
    --epoch 300 \
    --pre big \
    \
