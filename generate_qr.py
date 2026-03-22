#!/usr/bin/env python3
"""Generate QR code for proxy configuration."""

import qrcode


def generate_proxy_qr(
    host: str = "127.0.0.1",
    port: int = 1080,
    output_png: str = "qr_code.png",
    output_svg: str = "qr_code.svg",
) -> None:
    """Generate QR code for proxy configuration.

    Args:
        host: Proxy host
        port: Proxy port
        output_png: Output PNG file path
        output_svg: Output SVG file path
    """
    # Telegram proxy URL format
    data = f"socks5://{host}:{port}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_png)

    print(f"QR code generated: {output_png}, {output_svg}")
    print(f"Proxy URL: {data}")


if __name__ == "__main__":
    generate_proxy_qr()
