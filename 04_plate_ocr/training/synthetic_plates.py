import random
import cv2
import numpy as np
from pathlib import Path

INDIAN_STATES = ['GJ', 'MH', 'DL', 'KA', 'UP', 'HR', 'TN', 'KL', 'RJ', 'MP', 'AP', 'TS', 'WB']
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
DIGITS = '0123456789'


def generate_random_indian_plate_string() -> str:
    """Generates a syntactically valid Indian registration string."""
    r = random.random()
    if r < 0.80:
        # Standard State Format: e.g. GJ01AB1234
        st = random.choice(INDIAN_STATES)
        rto = f'{random.randint(1, 99):02d}'
        series = ''.join(random.choices(LETTERS, k=random.choice([1, 2])))
        num = f'{random.randint(1, 9999):04d}'
        return f'{st}{rto}{series}{num}'
    elif r < 0.95:
        # Bharat Series: e.g. 22BH1234AA
        yr = f'{random.randint(21, 26):02d}'
        num = f'{random.randint(1, 9999):04d}'
        series = ''.join(random.choices(LETTERS, k=2))
        return f'{yr}BH{num}{series}'
    else:
        # Commercial / Old style: e.g. GJ1A1234
        st = random.choice(INDIAN_STATES)
        rto = f'{random.randint(1, 9)}'
        series = ''.join(random.choices(LETTERS, k=1))
        num = f'{random.randint(1000, 9999)}'
        return f'{st}{rto}{series}{num}'


def render_synthetic_plate_image(text: str, width: int = 240, height: int = 60) -> np.ndarray:
    """Renders a synthetic plate crop with CCTV-style visual degradation."""
    # Background: 80% white private, 15% yellow commercial, 5% green EV
    r = random.random()
    if r < 0.80:
        bg_color = (random.randint(235, 255), random.randint(235, 255), random.randint(235, 255))
        text_color = (random.randint(10, 30), random.randint(10, 30), random.randint(10, 30))
    elif r < 0.95:
        bg_color = (random.randint(30, 60), random.randint(190, 230), random.randint(220, 255))
        text_color = (15, 15, 15)
    else:
        bg_color = (random.randint(40, 80), random.randint(150, 200), random.randint(30, 60))
        text_color = (245, 245, 245)

    img = np.full((height, width, 3), bg_color, dtype=np.uint8)

    # Outer border
    cv2.rectangle(img, (2, 2), (width - 3, height - 3), (20, 20, 20), 2)

    # Blue IND strip on the left (standard HSRP)
    cv2.rectangle(img, (4, 4), (22, height - 5), (180, 50, 20), -1)

    # Plate text font
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = height / 45.0
    thickness = max(1, int(font_scale * 2))

    # Text positioning
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    tx = max(26, (width - tw) // 2 + 10)
    ty = (height + th) // 2 - 2

    cv2.putText(img, text, (tx, ty), font, font_scale, text_color, thickness, cv2.LINE_AA)

    # Perturbations
    # 1. Motion blur or Gaussian blur
    if random.random() < 0.5:
        k = random.choice([3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)

    # 2. Gaussian Noise
    if random.random() < 0.4:
        noise = np.random.normal(0, random.uniform(5, 18), img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # 3. Brightness / contrast shift
    alpha = random.uniform(0.75, 1.25)
    beta = random.uniform(-20, 20)
    img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

    return img
