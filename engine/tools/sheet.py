"""Contact sheets and phone checks.
  sheet.py sheet OUT.jpg IMG... [--cols 4 --w 480]     labelled grid (label = file name)
  sheet.py phone OUT.jpg IMG...                         each image at 390 px wide (a 6" phone held upright
                                                        shows a 16:9 video ~390 px wide), side by side
  sheet.py video OUT.jpg VIDEO.mp4 [--fps 1 --cols 7]   1 frame per second from a video"""
import sys, os, subprocess, tempfile, glob, numpy as np, cv2

def label(im, s):
    cv2.putText(im, s, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(im, s, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return im

def grid(ims, cols):
    h = max(i.shape[0] for i in ims); w = max(i.shape[1] for i in ims)
    ims = [cv2.copyMakeBorder(i, 0, h-i.shape[0], 0, w-i.shape[1], cv2.BORDER_CONSTANT) for i in ims]
    while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
    rows = [np.hstack([cv2.copyMakeBorder(i, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(20, 20, 20)) for i in ims[r:r+cols]]) for r in range(0, len(ims), cols)]
    return np.vstack(rows)

def opt(a, k, d, f=int):
    return f(a[a.index(k)+1]) if k in a else d

def main():
    a = sys.argv[1:]; mode, out = a[0], a[1]
    files = [x for i, x in enumerate(a[2:], 2) if not x.startswith("--") and a[i-1] not in ("--cols", "--w", "--fps")]
    if mode == "video":
        fps = opt(a, "--fps", 1, float); cols = opt(a, "--cols", 7)
        d = tempfile.mkdtemp()
        subprocess.run(["ffmpeg", "-v", "error", "-i", files[0], "-vf", f"fps={fps},scale=480:-2", os.path.join(d, "%04d.png")], check=True)
        ims = [label(cv2.imread(f), f"{i/fps:.0f} s") for i, f in enumerate(sorted(glob.glob(os.path.join(d, "*.png"))))]
        cv2.imwrite(out, grid(ims, cols), [cv2.IMWRITE_JPEG_QUALITY, 86]); return
    if mode == "phone":
        ims = []
        for f in files:
            im = cv2.imread(f); s = 390/im.shape[1]
            ims.append(cv2.resize(im, (390, int(round(im.shape[0]*s))), interpolation=cv2.INTER_AREA))
        cv2.imwrite(out, grid(ims, opt(a, "--cols", 3)), [cv2.IMWRITE_JPEG_QUALITY, 92]); return
    w = opt(a, "--w", 480); cols = opt(a, "--cols", 4)
    ims = []
    for f in files:
        im = cv2.imread(f); s = w/im.shape[1]
        ims.append(label(cv2.resize(im, (w, int(round(im.shape[0]*s))), interpolation=cv2.INTER_AREA), os.path.splitext(os.path.basename(f))[0]))
    cv2.imwrite(out, grid(ims, cols), [cv2.IMWRITE_JPEG_QUALITY, 88])

if __name__ == "__main__":
    main()
