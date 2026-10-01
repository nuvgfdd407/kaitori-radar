"""共有用の画像（public/ogp.png、1200×630）を作る。

    pip install pillow
    python scripts/make_ogp_image.py

X（旧Twitter）や LINE でURLを共有したときに表示される画像。
サイト名や説明文を変えたときだけ作り直せばよい（自動更新では使わない）。
Windows の游ゴシック（なければメイリオ）で文字を描く。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).resolve().parent.parent / "public" / "ogp.png"
WIDTH, HEIGHT = 1200, 630
SCALE = 2  # 2倍の大きさで描いてから縮小し、線をなめらかにする

BRAND = (59, 91, 219)
TEXT = (28, 34, 44)
MUTED = (102, 112, 133)
BLIP = (255, 212, 59)
FONTS = [Path("C:/Windows/Fonts/YuGothB.ttc"), Path("C:/Windows/Fonts/meiryob.ttc")]


def main():
    font_path = next(p for p in FONTS if p.exists())
    s = SCALE
    img = Image.new("RGBA", (WIDTH * s, HEIGHT * s), "white")
    img = draw_radar(img, center=(250 * s, 300 * s), radius=165 * s)
    draw = ImageDraw.Draw(img)

    def font(size):
        return ImageFont.truetype(str(font_path), size * s)

    x = 470 * s
    draw.text((x, 170 * s), "買取レーダー", font=font(96), fill=TEXT)
    draw.text((x, 310 * s), "Switch 2・PS5・iPhoneの", font=font(40), fill=TEXT)
    draw.text((x, 365 * s), "新品買取価格を7店舗で比較", font=font(40), fill=TEXT)
    draw.text((x, 450 * s), "15分ごとに自動更新", font=font(30), fill=MUTED)
    draw.text((x, 520 * s), "kaitori-radar.com", font=font(30), fill=BRAND)
    draw.rectangle([0, (HEIGHT - 14) * s, WIDTH * s, HEIGHT * s], fill=BRAND)

    img.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(OUTPUT, optimize=True)
    print(f"作成しました: {OUTPUT}")


def draw_radar(img, center, radius):
    """サイトのロゴと同じ、レーダーのマーク。描き足した画像を返す。"""
    cx, cy = center
    r = radius
    ImageDraw.Draw(img).ellipse([cx - r, cy - r, cx + r, cy + r], fill=BRAND)

    # 半透明の白は、別の層に描いてから重ねる（直接描くと下の青が消えてしまう）
    rings = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(rings)
    for ring in (r * 2 / 3, r / 3):
        d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=(255, 255, 255, 115), width=int(r * 0.05))
    img = Image.alpha_composite(img, rings)

    # 真上から時計回りに60度の扇形（電波が走ったあと）
    sweep = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sweep).pieslice([cx - r, cy - r, cx + r, cy + r], start=270, end=330, fill=(255, 255, 255, 77))
    img = Image.alpha_composite(img, sweep)

    d = ImageDraw.Draw(img)
    d.line([(cx, cy), (cx + r * 0.866, cy - r * 0.5)], fill="white", width=int(r * 0.07))
    blip_x, blip_y, blip_r = cx + r * 0.4, cy - r * 0.33, r * 0.16
    d.ellipse([blip_x - blip_r, blip_y - blip_r, blip_x + blip_r, blip_y + blip_r], fill=BLIP)
    return img


if __name__ == "__main__":
    main()
