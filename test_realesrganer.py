import cv2
import numpy as np
from realesrgan.utils import RealESRGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact

import cv2
import numpy as np
import threading
from realesrgan.utils import RealESRGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact

def worker():
    print('Creating model...')
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    print('Creating upsampler...')
    upsampler = RealESRGANer(
        scale=4,
        model_path=['weights/realesr-general-x4v3.pth', 'weights/realesr-general-wdn-x4v3.pth'],
        dni_weight=[0.5, 0.5],
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=False,
        device='cpu',
    )
    print('Upsampler created')
    img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    print('Starting enhance...')
    output, _ = upsampler.enhance(img, outscale=4)
    print('Enhance finished!')

t = threading.Thread(target=worker)
t.start()
t.join()
print("Done")
