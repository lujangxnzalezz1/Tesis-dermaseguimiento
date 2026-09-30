"""Índice SSIM (RF-13): cuantifica cuánto mejora la similitud estructural al alinear las imágenes.
Implementación estándar de Wang et al. (2004) con ventana gaussiana 11x11, sigma 1,5."""
import cv2
import numpy as np


def ssim(a_bgr: np.ndarray, b_bgr: np.ndarray, mascara=None) -> float:
    a = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
    b = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY).astype(np.float64)
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    g = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)  # noqa: E731
    mu_a, mu_b = g(a), g(b)
    var_a, var_b, cov = g(a * a) - mu_a ** 2, g(b * b) - mu_b ** 2, g(a * b) - mu_a * mu_b
    mapa = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))
    if mascara is not None and mascara.any():
        return float(mapa[mascara].mean())
    return float(mapa.mean())
