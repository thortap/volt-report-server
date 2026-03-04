"""
Volt Sports Science — Report API
Recebe dados do formulário, gera PDF com layout completo e retorna o arquivo.
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageEnhance, ImageOps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io, os, base64, tempfile

app = Flask(__name__)
CORS(app)

# ── FONTES ────────────────────────────────────────────────────────────────────
BASE = os.path.dirname(__file__)
FONTS_PATH = os.path.join(BASE, 'fonts')

def register_fonts():
    variants = {
        'SG-Regular':   'StageGrotesk-Regular.ttf',
        'SG-Medium':    'StageGrotesk-Medium.ttf',
        'SG-Bold':      'StageGrotesk-Bold.ttf',
        'SG-ExtraBold': 'StageGrotesk-ExtraBold.ttf',
        'SG-Black':     'StageGrotesk-Black.ttf',
    }
    for name, fname in variants.items():
        path = os.path.join(FONTS_PATH, fname)
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))

register_fonts()

F_REG  = 'SG-Regular'  if os.path.exists(os.path.join(FONTS_PATH, 'StageGrotesk-Regular.ttf')) else 'Helvetica'
F_MED  = 'SG-Medium'   if os.path.exists(os.path.join(FONTS_PATH, 'StageGrotesk-Medium.ttf'))  else 'Helvetica'
F_BOLD = 'SG-Bold'     if os.path.exists(os.path.join(FONTS_PATH, 'StageGrotesk-Bold.ttf'))    else 'Helvetica-Bold'
F_XB   = 'SG-ExtraBold'if os.path.exists(os.path.join(FONTS_PATH, 'StageGrotesk-ExtraBold.ttf'))else 'Helvetica-Bold'
F_BLK  = 'SG-Black'    if os.path.exists(os.path.join(FONTS_PATH, 'StageGrotesk-Black.ttf'))   else 'Helvetica-Bold'

# ── CORES ─────────────────────────────────────────────────────────────────────
PW, PH = 210*mm, 297*mm
M = 14*mm

C_BG    = (14/255, 18/255, 14/255)
C_MID   = (28/255, 36/255, 28/255)
C_CARD  = (38/255, 48/255, 38/255)
C_GREEN = (46/255, 196/255, 113/255)
C_LIME  = (168/255, 224/255, 74/255)
C_WHITE = (1, 1, 1)
C_MUTED = (130/255, 155/255, 130/255)
C_WARN  = (255/255, 193/255, 7/255)
C_RED   = (244/255, 67/255, 54/255)
C_DARK  = (8/255, 10/255, 8/255)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def sf(c, rgb):  c.setFillColorRGB(*rgb)
def ss(c, rgb):  c.setStrokeColorRGB(*rgb)

def bg(c, col=C_BG):
    sf(c, col); c.rect(0, 0, PW, PH, fill=1, stroke=0)

def rr(c, x, y, w, h, r=3*mm, fc=C_CARD):
    sf(c, fc); c.roundRect(x, y, w, h, r, fill=1, stroke=0)

def txt(c, s, x, y, size, col=C_WHITE, font=None, align='left'):
    font = font or F_BOLD
    sf(c, col); c.setFont(font, size)
    if align == 'center': c.drawCentredString(x, y, s)
    elif align == 'right': c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)

def hline(c, x, y, w, col=C_GREEN, lw=1.5):
    ss(c, col); c.setLineWidth(lw); c.line(x, y, x+w, y)

def section_label(c, label, x, y, col=C_GREEN):
    sf(c, col); c.setFont(F_BOLD, 7.5)
    c.drawString(x, y, label.upper())
    hline(c, x, y-2, PW - x - M, col, 0.7)

def top_bar(c):
    sf(c, C_GREEN); c.rect(0, PH-3, PW, 3, fill=1, stroke=0)

def footer(c, page_num):
    sf(c, C_MID); c.rect(0, 0, PW, 11*mm, fill=1, stroke=0)
    txt(c, 'Volt Sports Science  |  Documento Confidencial', M, 4*mm, 6.5, C_MUTED, F_REG)
    if page_num:
        txt(c, str(page_num), PW - M, 4*mm, 6.5, C_MUTED, F_REG, 'right')
    # mini icon
    logo_path = os.path.join(BASE, 'assets', 'volt_icon_green.png')
    if os.path.exists(logo_path):
        icon = ImageReader(logo_path)
        c.saveState(); c.setFillAlpha(0.4)
        c.drawImage(icon, PW/2 - 3.5*mm, 2*mm, width=7*mm, height=7*mm, mask='auto')
        c.restoreState()

def draw_logo(c, x, y, w):
    logo_path = os.path.join(BASE, 'assets', 'volt_logo_transparent.png')
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        h = w * (1125/2000)
        c.drawImage(logo, x, y, width=w, height=h, mask='auto')

def draw_icon_bg(c, x, y, size, alpha=0.06):
    icon_path = os.path.join(BASE, 'assets', 'volt_icon_green.png')
    if os.path.exists(icon_path):
        icon = ImageReader(icon_path)
        c.saveState(); c.setFillAlpha(alpha)
        c.drawImage(icon, x, y, width=size, height=size, mask='auto')
        c.restoreState()

# ── FOTO P&B ──────────────────────────────────────────────────────────────────
def process_photo(photo_bytes):
    img = Image.open(io.BytesIO(photo_bytes))
    if img.mode == 'RGBA':
        bw_channel = ImageOps.grayscale(img.convert('RGB'))
        bw_channel = ImageEnhance.Contrast(bw_channel).enhance(1.25)
        bw_channel = ImageEnhance.Brightness(bw_channel).enhance(0.8)
        bw_rgb = Image.merge('RGB', [bw_channel]*3)
        # crop central para formato mais vertical
        w, h = bw_rgb.size
        crop_w = int(h * 0.75)
        left = max(0, (w - crop_w) // 2)
        bw_rgb = bw_rgb.crop((left, 0, min(w, left + crop_w), h))
        # remove bg
        arr = np.array(img)
        r2, g2, b2 = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        lum = (r2.astype(float)+g2+b2)/3
        sat = np.max(arr[:,:,:3], axis=2).astype(float) - np.min(arr[:,:,:3], axis=2)
        bg_mask = (lum > 190) & (sat < 30)
        alpha_ch = ImageOps.grayscale(Image.fromarray((~bg_mask * 255).astype(np.uint8)))
        result = Image.merge('RGBA', [*bw_rgb.split(), alpha_ch.crop((left,0,min(w,left+crop_w),h))])
    else:
        img = img.convert('RGB')
        bw = ImageOps.grayscale(img)
        bw = ImageEnhance.Contrast(bw).enhance(1.25)
        bw = ImageEnhance.Brightness(bw).enhance(0.8)
        w, h = img.size
        crop_w = int(h * 0.75)
        left = max(0, (w - crop_w) // 2)
        result = Image.merge('RGB', [bw]*3).crop((left, 0, min(w, left+crop_w), h))

    buf = io.BytesIO(); result.save(buf, 'PNG'); buf.seek(0)
    return ImageReader(buf)

# ── GRÁFICOS ──────────────────────────────────────────────────────────────────
def bar_chart(vals, labels, colors_hex, title, unit=''):
    fig, ax = plt.subplots(figsize=(380/96, 130/96))
    fig.patch.set_facecolor('#0E120E')
    ax.set_facecolor('#0E120E')
    ax.barh(labels, vals, color=colors_hex, height=0.45)
    mx = max(vals) if vals else 1
    for i, (v, lbl) in enumerate(zip(vals, labels)):
        ax.text(v + mx*0.04, i, f'{v}{unit}', va='center', color='white', fontsize=9, fontweight='bold')
    ax.set_xlim(0, mx*1.4)
    ax.set_title(title, color='#2EC471', fontsize=8.5, pad=4, loc='left', fontweight='bold')
    ax.tick_params(colors='#82A082', labelsize=8.5)
    for sp in ax.spines.values(): sp.set_color('#1C241C')
    ax.grid(axis='x', color='#1C241C', linewidth=0.6)
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor())
    plt.close(); buf.seek(0)
    return ImageReader(buf)

def wellness_gauge(score, max_s=25):
    pct = score / max_s
    col = '#2EC471' if score <= 12 else ('#FFC107' if score <= 18 else '#F44336')
    fig, ax = plt.subplots(figsize=(280/96, 200/96), subplot_kw=dict(aspect='equal'))
    fig.patch.set_facecolor('#0E120E')
    ax.set_facecolor('#0E120E')
    th = np.linspace(np.pi, 0, 300)
    ax.plot(np.cos(th), np.sin(th), color='#1C241C', linewidth=18, solid_capstyle='round')
    tv = np.linspace(np.pi, np.pi - pct*np.pi, 300)
    ax.plot(np.cos(tv), np.sin(tv), color=col, linewidth=18, solid_capstyle='round')
    ax.text(0, 0.08, str(score), ha='center', va='center', color='white', fontsize=32, fontweight='bold')
    ax.text(0, -0.28, f'/ {max_s}', ha='center', color='#82A082', fontsize=10)
    ax.set_xlim(-1.4, 1.4); ax.set_ylim(-0.6, 1.3); ax.axis('off')
    plt.tight_layout(pad=0.1)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor())
    plt.close(); buf.seek(0)
    return ImageReader(buf)

def readiness_chart(weeks_vals, prev_avg, title, unit):
    labels = [f'S{i+1}' for i, v in enumerate(weeks_vals) if v is not None]
    vals   = [v for v in weeks_vals if v is not None]
    if not vals: return None
    fig, ax = plt.subplots(figsize=(380/96, 120/96))
    fig.patch.set_facecolor('#0E120E')
    ax.set_facecolor('#0E120E')
    ax.plot(labels, vals, color='#2EC471', linewidth=2.5, marker='o', markersize=5)
    ax.fill_between(labels, vals, alpha=0.1, color='#2EC471')
    if prev_avg:
        ax.axhline(prev_avg, color='#506050', linewidth=1.5, linestyle='--', label=f'Mês ant. ({prev_avg}{unit})')
        ax.legend(fontsize=7.5, facecolor='#0E120E', edgecolor='#1C241C', labelcolor='#82A082')
    ax.set_title(title, color='#2EC471', fontsize=8.5, pad=4, loc='left', fontweight='bold')
    ax.tick_params(colors='#82A082', labelsize=8.5)
    for sp in ax.spines.values(): sp.set_color('#1C241C')
    ax.grid(axis='y', color='#1C241C', linewidth=0.6)
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor())
    plt.close(); buf.seek(0)
    return ImageReader(buf)

# ── GERADOR DE PDF ────────────────────────────────────────────────────────────
def generate_pdf(d, photo_ir):
    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=(PW, PH))
    cv.setTitle(f"Volt Report - {d['nome']} - {d['mes']} {d['ano']}")

    # ── CAPA ──────────────────────────────────────────────────────────────────
    bg(cv, C_DARK)

    if photo_ir:
        photo_h = PH * 0.58
        cv.drawImage(photo_ir, 114.5, 0, width=PW, height=photo_h,
                     preserveAspectRatio=True, anchor='sw', mask='auto')
        for i in range(50):
            alpha = (i/50)**1.2
            sf(cv, C_DARK); cv.setFillAlpha(alpha * 0.92)
            strip = photo_h / 50
            cv.rect(0, photo_h - (i+1)*strip, PW, strip+1, fill=1, stroke=0)
        cv.setFillAlpha(1)
        for i in range(30):
            alpha = 1 - (i/30)**0.7
            sf(cv, C_DARK); cv.setFillAlpha(alpha * 0.9)
            strip = photo_h * 0.35 / 30
            cv.rect(0, i*strip, PW, strip+1, fill=1, stroke=0)
        cv.setFillAlpha(1)
        sf(cv, C_DARK); cv.rect(0, photo_h - 2, PW, PH - photo_h + 4, fill=1, stroke=0)

    sf(cv, C_GREEN); cv.rect(0, PH-4, PW, 4, fill=1, stroke=0)
    draw_logo(cv, M - 15.46*mm, PH - 32*mm, w=58*mm)
    draw_icon_bg(cv, PW - 38*mm, PH - 42*mm, 34*mm, alpha=0.08)

    sf(cv, C_WHITE); cv.setFont(F_BOLD, 48)
    cv.drawString(M, PH*0.72, 'REPORT')
    cv.setFont(F_BOLD, 26)
    cv.drawString(M, PH*0.72 - 32, 'MENSAL')
    hline(cv, M, PH*0.72 - 70, PW - 2*M, C_GREEN, 1.2)

    txt(cv, 'DOCUMENTO CONFIDENCIAL', M, PH*0.72 - 50, 8, C_MUTED, F_REG)
    sf(cv, C_WHITE); cv.setFont(F_BOLD, 16)
    cv.drawString(M, PH*0.72 - 88, d['nome'].upper())
    sf(cv, C_GREEN); cv.setFont(F_BOLD, 11)
    cv.drawString(M, PH*0.72 - 104, f"{d['mes'].upper()} / {d['ano']}")

    footer(cv, '')
    cv.showPage()

    # ── JOGOS & DISPONIBILIDADE ───────────────────────────────────────────────
    bg(cv); top_bar(cv)
    draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm)

    y = PH - 22*mm
    section_label(cv, '01 — Jogos', M, y)

    cw = (PW - 2*M - 4*mm) / 2
    cy = y - 38*mm
    for i, (val, lbl, sub, col) in enumerate([
        (d['jogosParticipou'], 'JOGOS', f"{d['mes']} {d['ano']}", C_GREEN),
        (d['jogosAnterior'],   'JOGOS', d['mesAnterior'], C_MUTED),
    ]):
        cx = M + i*(cw + 4*mm)
        rr(cv, cx, cy, cw, 32*mm, fc=C_CARD)
        sf(cv, col); cv.roundRect(cx, cy, 2.5*mm, 32*mm, 1.5*mm, fill=1, stroke=0)
        sf(cv, col); cv.setFont(F_BOLD, 36)
        cv.drawString(cx + 8*mm, cy + 18*mm, str(val))
        txt(cv, lbl, cx + 8*mm, cy + 10*mm, 8, C_WHITE, F_BOLD)
        txt(cv, sub, cx + 8*mm, cy + 4*mm, 7.5, C_MUTED, F_REG)

    jogos_chart = bar_chart(
        [d['jogosParticipou'], d['jogosAnterior']],
        [f"{d['mes']}/{d['ano']}", d['mesAnterior']],
        ['#2EC471','#506050'], 'JOGOS DISPUTADOS'
    )
    cv.drawImage(jogos_chart, M, cy - 55*mm, width=PW - 2*M, height=38*mm)

    y2 = cy - 65*mm
    hline(cv, M, y2, PW - 2*M, C_MUTED, 0.4)
    section_label(cv, '02 — Disponibilidade', M, y2 - 8*mm)

    disp = d['disponibilidade']
    disp_col = C_GREEN if disp >= 80 else (C_WARN if disp >= 50 else C_RED)
    rr(cv, M, y2 - 50*mm, PW - 2*M, 38*mm, fc=C_CARD)
    sf(cv, disp_col); cv.setFont(F_BOLD, 52)
    cv.drawCentredString(PW/2, y2 - 26*mm, f'{disp}%')
    txt(cv, f"{d['jogosParticipou']} de {d['jogosPossiveis']} jogos possíveis",
        PW/2, y2 - 36*mm, 9, C_MUTED, F_REG, 'center')
    txt(cv, 'DISPONIBILIDADE NO MÊS', PW/2, y2 - 44*mm, 7.5, C_MUTED, F_BOLD, 'center')

    bar_y = y2 - 70*mm
    rr(cv, M, bar_y, PW - 2*M, 17*mm, fc=C_CARD)
    txt(cv, 'MINUTOS JOGADOS', M + 4*mm, bar_y + 10*mm, 7.5, C_WHITE, F_BOLD)
    bw2 = PW - 2*M - 8*mm
    mp  = d['minutosPossiveis']
    pct = d['minutosJogados'] / mp if mp > 0 else 0
    rr(cv, M + 4*mm, bar_y + 3*mm, bw2, 5*mm, r=2*mm, fc=C_MID)
    rr(cv, M + 4*mm, bar_y + 3*mm, bw2*pct, 5*mm, r=2*mm, fc=C_GREEN)
    txt(cv, f"{d['minutosJogados']} min", M + 4*mm + bw2*pct + 2*mm, bar_y + 5*mm, 7.5, C_WHITE, F_BOLD)
    diff_min = d['minutosJogados'] - d['minutosAnterior']
    diff_str = f"{'+'if diff_min>=0 else ''}{diff_min} min vs {d['mesAnterior']}"
    diff_col = C_GREEN if diff_min >= 0 else C_RED
    txt(cv, diff_str, M + 4*mm, bar_y + 0.5*mm, 7, diff_col, F_REG)

    footer(cv, 2)
    cv.showPage()

    # ── ATIVIDADES & WELLNESS ─────────────────────────────────────────────────
    bg(cv); top_bar(cv)
    draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm)

    y = PH - 22*mm
    section_label(cv, '03 — Atividades Realizadas', M, y)

    ativs = [
        (d['sessTreino'], 'TREINO EM CASA', 'Protocolo individual supervisionado pela Volt', C_GREEN),
        (d['sessMed'],    'MEDICINA',       'Consultas e avaliações clínicas', C_LIME),
        (d['sessPsi'],    'PSICOLOGIA',     'Sessões de suporte psicológico', C_GREEN),
        (d['sessNut'],    'NUTRIÇÃO',       'Acompanhamento nutricional', C_LIME),
    ]
    for i, (num, title, desc, col) in enumerate(ativs):
        if num == 0: continue
        ay = y - 14*mm - i*30*mm
        rr(cv, M, ay - 24*mm, PW - 2*M, 22*mm, fc=C_CARD)
        sf(cv, col); cv.roundRect(M, ay - 24*mm, 2.5*mm, 22*mm, 1.5*mm, fill=1, stroke=0)
        sf(cv, col); cv.setFont(F_BOLD, 28)
        cv.drawString(M + 5*mm, ay - 10*mm, str(num).zfill(2))
        txt(cv, title, M + 24*mm, ay - 7*mm, 9, C_WHITE, F_BOLD)
        txt(cv, desc,  M + 24*mm, ay - 15*mm, 7.5, C_MUTED, F_REG)

    total = d['sessTreino'] + d['sessMed'] + d['sessPsi'] + d['sessNut']
    ty = y - 14*mm - 4*30*mm + 10*mm
    rr(cv, M, ty, PW - 2*M, 10*mm, r=2*mm, fc=C_MID)
    txt(cv, 'TOTAL DE ATIVIDADES NO MÊS', M + 4*mm, ty + 6.5*mm, 8, C_MUTED, F_BOLD)
    txt(cv, str(total), PW - M - 4*mm, ty + 6.5*mm, 11, C_GREEN, F_BOLD, 'right')

    div_y = ty - 10*mm
    hline(cv, M, div_y, PW - 2*M, C_MUTED, 0.4)

    section_label(cv, '04 — Wellness Score', M, div_y - 8*mm)

    g_y = div_y - 62*mm
    w_gauge = wellness_gauge(d['wellness'], max_s=25)
    cv.drawImage(w_gauge, PW/2 - 28*mm, g_y, width=56*mm, height=40*mm)

    w_score = d['wellness']
    w_label = 'BOM' if w_score <= 12 else ('MÉDIO' if w_score <= 18 else 'RUIM')
    w_col   = C_GREEN if w_score <= 12 else (C_WARN if w_score <= 18 else C_RED)

    scale_y = g_y - 18*mm
    scale_items = [('1–12', 'BOM', C_GREEN), ('13–18', 'MÉDIO', C_WARN), ('19–25', 'RUIM', C_RED)]
    sw = (PW - 2*M - 4*mm) / 3
    active_i = 0 if w_score <= 12 else (1 if w_score <= 18 else 2)
    for i, (rng, lbl, col) in enumerate(scale_items):
        sx = M + i*(sw + 2*mm)
        rr(cv, sx, scale_y - 14*mm, sw, 12*mm, r=2.5*mm, fc=col if i == active_i else C_CARD)
        tc = C_DARK if i == active_i else col
        txt(cv, rng, sx + sw/2, scale_y - 6*mm, 9, tc, F_BOLD, 'center')
        txt(cv, lbl, sx + sw/2, scale_y - 12*mm, 6.5, tc, F_BOLD, 'center')

    rr(cv, M, scale_y - 30*mm, PW - 2*M, 12*mm, r=2*mm, fc=C_MID)
    txt(cv, f'Score {w_score}/25 — {w_label}', M + 4*mm, scale_y - 22*mm, 8, w_col, F_BOLD)
    txt(cv, 'Média de: sono, humor, fadiga, estresse e dor muscular',
        M + 4*mm, scale_y - 28*mm, 7, C_MUTED, F_REG)

    footer(cv, 3)
    cv.showPage()

    # ── READINESS ─────────────────────────────────────────────────────────────
    has_cmj = any(v is not None for v in d['cmj'])
    has_hrv = any(v is not None for v in d['hrv'])

    if has_cmj or has_hrv:
        bg(cv); top_bar(cv)
        draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm)

        y = PH - 22*mm
        section_label(cv, '05 — Readiness', M, y)

        ry = y - 10*mm
        if has_cmj:
            cmj_vals = [v for v in d['cmj'] if v is not None]
            cmj_chart = readiness_chart(d['cmj'], d.get('cmjAnterior'), 'CMJ — ALTURA DO SALTO', ' cm')
            if cmj_chart:
                cv.drawImage(cmj_chart, M, ry - 46*mm, width=PW - 2*M, height=40*mm)

            rr(cv, M, ry - 58*mm, PW - 2*M, 10*mm, r=2*mm, fc=C_CARD)
            if d.get('cmjAnterior') and cmj_vals:
                avg = sum(cmj_vals)/len(cmj_vals)
                diff = ((avg - d['cmjAnterior'])/d['cmjAnterior']*100)
                diff_col = C_GREEN if diff >= 0 else C_RED
                txt(cv, f"Média do mês: {avg:.1f} cm", M + 4*mm, ry - 52*mm, 8, C_WHITE, F_BOLD)
                txt(cv, f"{'+'if diff>=0 else ''}{diff:.1f}% vs {d['mesAnterior']}", PW-M-4*mm, ry - 52*mm, 8, diff_col, F_BOLD, 'right')
            if d.get('cmjObs'):
                txt(cv, d['cmjObs'], M + 4*mm, ry - 56*mm, 7, C_MUTED, F_REG)
            ry -= 66*mm

        if has_hrv:
            hrv_vals = [v for v in d['hrv'] if v is not None]
            hrv_chart = readiness_chart(d['hrv'], d.get('hrvAnterior'), 'HRV — VARIABILIDADE CARDÍACA', ' ms')
            if hrv_chart:
                cv.drawImage(hrv_chart, M, ry - 46*mm, width=PW - 2*M, height=40*mm)

            rr(cv, M, ry - 58*mm, PW - 2*M, 10*mm, r=2*mm, fc=C_CARD)
            if d.get('hrvAnterior') and hrv_vals:
                avg = sum(hrv_vals)/len(hrv_vals)
                diff = ((avg - d['hrvAnterior'])/d['hrvAnterior']*100)
                diff_col = C_GREEN if diff >= 0 else C_RED
                txt(cv, f"Média do mês: {avg:.1f} ms", M + 4*mm, ry - 52*mm, 8, C_WHITE, F_BOLD)
                txt(cv, f"{'+'if diff>=0 else ''}{diff:.1f}% vs {d['mesAnterior']}", PW-M-4*mm, ry - 52*mm, 8, diff_col, F_BOLD, 'right')
            if d.get('hrvObs'):
                txt(cv, d['hrvObs'], M + 4*mm, ry - 56*mm, 7, C_MUTED, F_REG)

        footer(cv, 4)
        cv.showPage()

    # ── PONTOS DE ATENÇÃO & NÃO ATINGIMOS ────────────────────────────────────
    bg(cv); top_bar(cv)
    draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm)

    page_n = 5 if (has_cmj or has_hrv) else 4
    y = PH - 22*mm

    if d.get('pontosAtencao'):
        section_label(cv, '06 — Pontos de Atenção', M, y, C_WARN)
        lines = d['pontosAtencao']
        box_h = max(40*mm, len(lines)//3 * mm + 40*mm)
        rr(cv, M, y - box_h - 10*mm, PW - 2*M, box_h, fc=C_CARD)
        sf(cv, C_WARN); cv.roundRect(M, y - box_h - 10*mm, 3*mm, box_h, 1.5*mm, fill=1, stroke=0)
        rr(cv, M + 6*mm, y - 22*mm, 10*mm, 10*mm, r=5*mm, fc=C_WARN)
        txt(cv, '!', M + 11*mm, y - 16*mm, 9, C_DARK, F_BOLD, 'center')
        txt(cv, 'PONTOS DE ATENÇÃO', M + 20*mm, y - 16*mm, 10, C_WHITE, F_BOLD)

        # wrap text
        words = lines.split()
        line, line_y = [], y - 28*mm
        for word in words:
            test = ' '.join(line + [word])
            if cv.stringWidth(test, F_REG, 8.5) > (PW - 2*M - 14*mm):
                txt(cv, ' '.join(line), M + 8*mm, line_y, 8.5, C_WHITE, F_REG)
                line = [word]; line_y -= 5*mm
            else:
                line.append(word)
        if line:
            txt(cv, ' '.join(line), M + 8*mm, line_y, 8.5, C_WHITE, F_REG)

        y = y - box_h - 18*mm

    if d.get('naoAtingimos'):
        section_label(cv, '07 — Não Atingimos', M, y, C_RED)
        lines = d['naoAtingimos']
        box_h = max(40*mm, len(lines)//3 * mm + 40*mm)
        rr(cv, M, y - box_h - 10*mm, PW - 2*M, box_h, fc=C_CARD)
        sf(cv, C_RED); cv.roundRect(M, y - box_h - 10*mm, 3*mm, box_h, 1.5*mm, fill=1, stroke=0)
        rr(cv, M + 6*mm, y - 22*mm, 10*mm, 10*mm, r=5*mm, fc=C_RED)
        txt(cv, 'X', M + 11*mm, y - 16*mm, 9, C_WHITE, F_BOLD, 'center')
        txt(cv, 'NÃO ATINGIMOS', M + 20*mm, y - 16*mm, 10, C_WHITE, F_BOLD)

        words = lines.split()
        line, line_y = [], y - 28*mm
        for word in words:
            test = ' '.join(line + [word])
            if cv.stringWidth(test, F_REG, 8.5) > (PW - 2*M - 14*mm):
                txt(cv, ' '.join(line), M + 8*mm, line_y, 8.5, C_WHITE, F_REG)
                line = [word]; line_y -= 5*mm
            else:
                line.append(word)
        if line:
            txt(cv, ' '.join(line), M + 8*mm, line_y, 8.5, C_WHITE, F_REG)

    footer(cv, page_n)
    cv.showPage()

    # ── ENCERRAMENTO ──────────────────────────────────────────────────────────
    bg(cv, C_DARK)
    if photo_ir:
        cv.saveState(); cv.setFillAlpha(0.2)
        cv.drawImage(photo_ir, 0, PH*0.25, width=PW, height=PH*0.75,
                     preserveAspectRatio=False, mask='auto')
        cv.restoreState()
        sf(cv, C_DARK); cv.setFillAlpha(0.72)
        cv.rect(0, 0, PW, PH, fill=1, stroke=0)
        cv.setFillAlpha(1)

    sf(cv, C_GREEN); cv.rect(0, PH-4, PW, 4, fill=1, stroke=0)
    logo_w = 60*mm
    draw_logo(cv, PW/2 - logo_w/2, PH*0.55, w=logo_w)
    hline(cv, PW/2 - 30*mm, PH*0.52, 60*mm, C_GREEN, 1)
    txt(cv, 'FOR THE ATHLETE,', PW/2, PH*0.47, 13, C_WHITE, F_BOLD, 'center')
    txt(cv, 'BY THE ATHLETE.', PW/2, PH*0.43, 13, C_WHITE, F_BOLD, 'center')
    txt(cv, f"Próximo relatório: {d['mesProximo']} / {d['ano']}", PW/2, PH*0.37, 9, C_MUTED, F_REG, 'center')
    draw_icon_bg(cv, PW/2 - 18*mm, PH*0.14, 36*mm, alpha=0.12)
    txt(cv, '@voltsportsscience', PW/2, 28*mm, 9, C_MUTED, F_REG, 'center')
    txt(cv, 'contato@voltsportsscience.com', PW/2, 20*mm, 8.5, C_MUTED, F_REG, 'center')
    txt(cv, '#changethegame', PW/2, 12*mm, 8, C_GREEN, F_BOLD, 'center')
    cv.showPage()

    cv.save()
    buf.seek(0)
    return buf

# ── ROTA PRINCIPAL ────────────────────────────────────────────────────────────
@app.route('/generate', methods=['POST'])
def generate():
    try:
        data    = request.form.to_dict()
        photo_f = request.files.get('photo')

        # parse campos
        def fi(k, default=0): return int(data.get(k, default) or default)
        def ff(k): v = data.get(k); return float(v) if v else None
        def fs(k): return data.get(k, '')

        cmj = [ff(f'cmj{i}') for i in range(1,5)]
        hrv = [ff(f'hrv{i}') for i in range(1,5)]

        meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                 'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
        mes_atual = fs('mes')
        idx = meses.index(mes_atual) if mes_atual in meses else 0
        mes_proximo = meses[(idx + 1) % 12]

        jogos_p = fi('jogosParticipou')
        jogos_pos = fi('jogosPossiveis')
        disp = round((jogos_p / jogos_pos * 100)) if jogos_pos > 0 else 0

        d = {
            'nome': f"{fs('firstName')} {fs('lastName')}".strip(),
            'clube': fs('clube'),
            'posicao': fs('posicao'),
            'mes': mes_atual,
            'mesAnterior': fs('mesAnterior'),
            'mesProximo': mes_proximo,
            'ano': fs('ano'),
            'jogosParticipou': jogos_p,
            'jogosPossiveis': jogos_pos,
            'jogosAnterior': fi('jogosAnterior'),
            'minutosJogados': fi('minutosJogados'),
            'minutosPossiveis': fi('minutosPossiveis'),
            'minutosAnterior': fi('minutosAnterior'),
            'disponibilidade': disp,
            'sessTreino': fi('sessTreino'),
            'sessMed': fi('sessMed'),
            'sessPsi': fi('sessPsi'),
            'sessNut': fi('sessNut'),
            'wellness': fi('wellness'),
            'cmj': cmj,
            'cmjAnterior': ff('cmjAnterior'),
            'cmjObs': fs('cmjObs'),
            'hrv': hrv,
            'hrvAnterior': ff('hrvAnterior'),
            'hrvObs': fs('hrvObs'),
            'pontosAtencao': fs('pontosAtencao'),
            'naoAtingimos': fs('naoAtingimos'),
        }

        photo_ir = None
        if photo_f:
            photo_ir = process_photo(photo_f.read())

        pdf_buf = generate_pdf(d, photo_ir)
        filename = f"Volt_Report_{d['nome'].replace(' ','_')}_{d['mes']}{d['ano']}.pdf"

        return send_file(
            pdf_buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Volt Report Generator'})

@app.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Volt Report API — use POST /generate'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
