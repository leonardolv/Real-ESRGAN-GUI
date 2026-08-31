import os
import sys
import time
from PIL import Image
from queue import Queue

import sys

# Prevent OpenMP/MKL thread deadlocks when using PyTorch CPU inference on Windows
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
import cv2
cv2.setNumThreads(0)
import torch
torch.set_num_threads(1)

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.controllers.model_manager import ModelManager
from gui.controllers.upscale_controller import UpscaleController, MsgType, UpscaleJob

def run_test():
    # 1. Create a sample image
    test_img_path = "test_input.jpg"
    out_img_path = "test_input_out.jpg"
    img = Image.new('RGB', (64, 64), color = 'red')
    img.save(test_img_path)

    print("Sample image created.")

    # 2. Setup controllers
    mm = ModelManager()
    ctrl = UpscaleController(mm)

    messages = Queue()
    def on_msg(msg):
        messages.put(msg)
        print(f"[Worker] {msg.type.name}: {msg.data}")

    ctrl.on_message = on_msg

    # 3. Add job
    job = UpscaleJob(
        input_path='test_video.mp4',
        output_path='test_video_out.mp4',
        model_name="realesr-animevideov3",
        outscale=4.0,
        denoise_strength=0.5,
        face_enhance=False
    )
    print("Job added, running in worker thread...")
    ctrl.submit(job)

    # 4. Wait for completion
    while True:
        msgs = ctrl.poll()
        if not msgs:
            time.sleep(0.1)
            continue
            
        done = False
        for msg in msgs:
            print(f"[Worker] {msg.type.name}: {msg.data}")
            if msg.type == MsgType.COMPLETE:
                print("Test successful!")
                done = True
                break
            elif msg.type == MsgType.ERROR:
                print(f"Test failed: {msg.data}")
                sys.exit(1)
        if done:
            break

    # Cleanup
    import shutil
    if os.path.exists(test_img_path):
        os.remove(test_img_path)
    if os.path.exists('test_video.mp4'):
        try: os.remove('test_video.mp4')
        except: pass
    if os.path.exists('test_video_out.mp4'):
        try: shutil.rmtree('test_video_out.mp4')
        except: pass
    if os.path.exists(out_img_path):
        try: shutil.rmtree(out_img_path)
        except: pass

if __name__ == "__main__":
    run_test()
