"""Soft light pool on Seliu (island + reef, wide falloff) used by the renderer's grade -> data/L2_light.npy"""
import numpy as np, cv2
a = np.load("data/L2_comp.npy", mmap_mode="r"); land = (np.array(a[3]) > 0.5).astype(np.uint8)
n, lab = cv2.connectedComponents(land, connectivity=8); isl = (lab == lab[3250, 3090]).astype(np.uint8)  # Seliu
core = cv2.GaussianBlur(cv2.dilate(isl, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (101, 101))).astype(np.float32), (0, 0), 40)
wide = cv2.GaussianBlur(cv2.dilate(isl, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (161, 161))).astype(np.float32), (0, 0), 80)
np.save("data/L2_light.npy", np.clip(0.75*core+0.35*wide, 0, 1).astype(np.float32))
