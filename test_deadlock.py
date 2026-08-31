import cv2
import torch
import numpy as np
import threading
from realesrgan.archs.srvgg_arch import SRVGGNetCompact

def worker():
    print("Worker started")
    img = cv2.imread('test_input.jpg')
    print("Image read")
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    print("Model created")
    x = torch.from_numpy(img).float().permute(2, 0, 1).unsqueeze(0)
    print("Input created")
    y = model(x)
    print("Output generated")

t = threading.Thread(target=worker)
t.start()
t.join()
print("Done")
