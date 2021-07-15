#!/bin/bash

python train.py \
    --dataset cora \
    --attack meta \
    --ptb_rate 0.1 \
    --epoch 300 \
    --pre big \
    \
