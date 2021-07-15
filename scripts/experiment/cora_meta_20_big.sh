#!/bin/bash

python train.py \
    --dataset cora \
    --attack meta \
    --ptb_rate 0.2 \
    --epoch 300 \
    --pre big \
    \
