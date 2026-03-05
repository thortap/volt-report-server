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

    # ── helpers ──
    def page_cover():
        bg(cv, C_DARK)
        if photo_ir:
            photo_h = PH * 0.58
            cv.drawImage(photo_ir, 114.5, 0, width=PW, height=photo_h, preserveAspectRatio=True, anchor='sw', mask='auto')
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
        draw_icon_bg(cv, PW - 38*mm, PH - 42*mm, 34*mm, alpha=0.28)
        sf(cv, C_WHITE); cv.setFont(F_BOLD, 48)
        cv.drawString(M, PH*0.72, 'REPORT')
        cv.setFont(F_BOLD, 26)
        cv.drawString(M, PH*0.72 - 32, 'MENSAL')
        hline(cv, M, PH*0.72 - 70, PW - 2*M, C_GREEN, 1.2)
        sf(cv, C_WHITE); cv.setFont(F_BOLD, 16)
        cv.drawString(M, PH*0.72 - 88, d['nome'].upper())
        sf(cv, C_GREEN); cv.setFont(F_BOLD, 11)
        cv.drawString(M, PH*0.72 - 104, f"{d['mes'].upper()} / {d['ano']}")
        txt(cv, 'DOCUMENTO CONFIDENCIAL', M, PH*0.72 - 50, 8, C_MUTED, F_REG)
        footer(cv, '')

    def page_jogos():
        bg(cv); top_bar(cv)
        draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm, alpha=0.06)
        y = PH - 22*mm

        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y, '01 — JOGOS')
        hline(cv, M, y - 3, PW - 2*M, C_GREEN, 0.7)

        jogos_p  = d['jogosParticipou']
        jogos_a  = d['jogosAnterior']
        mes_a    = d['mesAnterior']
        jogos_ir = bar_chart([jogos_a, jogos_p],
                           [mes_a, d['mes']],
                           ['#506050', '#2EC471'], 'JOGOS DISPUTADOS')
        cv.drawImage(jogos_ir, M, y - 56*mm, width=PW - 2*M, height=52*mm)

        cy = y - 56*mm
        y2 = cy - 16*mm
        hline(cv, M, y2, PW - 2*M, C_MUTED, 0.4)

        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y2 - 8*mm, '02 — DISPONIBILIDADE')
        hline(cv, M, y2 - 11*mm, PW - 2*M, C_GREEN, 0.7)

        disp = d['disponibilidade']
        rr(cv, M, y2 - 50*mm, PW - 2*M, 38*mm, fc=C_CARD)
        sf(cv, C_GREEN); cv.setFont(F_BOLD, 52)
        cv.drawCentredString(PW/2, y2 - 26*mm, f'{disp}%')
        txt(cv, f"{d['jogosParticipou']} de {d['jogosPossiveis']} jogos possíveis", PW/2, y2 - 36*mm, 9, C_MUTED, F_REG, 'center')
        txt(cv, d['mes'].upper(), PW/2, y2 - 44*mm, 7.5, C_MUTED, F_BOLD, 'center')

        bar_y = y2 - 70*mm
        mp  = d['minutosPossiveis']
        mj  = d['minutosJogados']
        ma  = d['minutosAnterior']
        pct_bar = mj / mp if mp > 0 else 0
        rr(cv, M, bar_y, PW - 2*M, 17*mm, fc=C_CARD)
        txt(cv, 'MINUTOS JOGADOS', M + 4*mm, bar_y + 10*mm, 7.5, C_WHITE, F_BOLD)
        bw2 = PW - 2*M - 8*mm
        rr(cv, M + 4*mm, bar_y + 3*mm, bw2, 5*mm, r=2*mm, fc=C_MID)
        rr(cv, M + 4*mm, bar_y + 3*mm, bw2*pct_bar, 5*mm, r=2*mm, fc=C_GREEN)
        txt(cv, f'{mj} min', M + 4*mm + bw2*pct_bar + 2*mm, bar_y + 5*mm, 7.5, C_WHITE, F_BOLD)
        diff_min = mj - ma
        txt(cv, f"{'+'if diff_min>=0 else ''}{diff_min} min vs {mes_a}", M + 4*mm, bar_y + 0.5*mm, 7, C_MUTED, F_REG)

        mins_ir = bar_chart([mj, ma], [d['mes'], mes_a], ['#2EC471','#506050'], 'MINUTOS JOGADOS', ' min')
        cv.drawImage(mins_ir, M, bar_y - 52*mm, width=PW - 2*M, height=48*mm)
        footer(cv, '2')

    def page_atividades():
        bg(cv); top_bar(cv)
        draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm, alpha=0.06)
        y = PH - 22*mm

        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y, '03 — ATIVIDADES REALIZADAS')
        hline(cv, M, y - 3, PW - 2*M, C_GREEN, 0.7)

        atividades = [
            (str(d['sessTreino']), 'SESSÕES DE TREINO EM CASA ~', 'Sessões preventivas individualizadas', C_GREEN),
            (str(d['sessMed']),    'MEDICINA DO ESPORTE',         'Avaliação clínica de rotina, sem intercorrências', C_LIME),
        ]
        if d['sessPsi'] > 0:
            atividades.append((str(d['sessPsi']), 'PSICOLOGIA', 'Sessões de suporte psicológico', C_GREEN))
        if d['sessNut'] > 0:
            atividades.append((str(d['sessNut']), 'NUTRIÇÃO', 'Acompanhamento nutricional', C_LIME))

        for i, (num, title, desc, col) in enumerate(atividades):
            ay = y - 22*mm - i*36*mm
            rr(cv, M, ay - 28*mm, PW - 2*M, 26*mm, fc=C_CARD)
            sf(cv, col); cv.setFont(F_BOLD, 34)
            cv.drawString(M + 5*mm, ay - 12*mm, num)
            txt(cv, title, M + 26*mm, ay - 8*mm, 9.5, C_WHITE, F_BOLD)
            txt(cv, desc,  M + 26*mm, ay - 17*mm, 8, C_MUTED, F_REG)
            sf(cv, col); cv.roundRect(M, ay - 28*mm, 2.5*mm, 26*mm, 1.5*mm, fill=1, stroke=0)

        total = d['sessTreino'] + d['sessMed'] + d['sessPsi'] + d['sessNut']
        ty = y - 22*mm - len(atividades)*36*mm - 4*mm
        rr(cv, M, ty - 12*mm, PW - 2*M, 10*mm, r=2*mm, fc=C_MID)
        txt(cv, 'TOTAL DE ATIVIDADES NO MÊS', M + 4*mm, ty - 7*mm, 8, C_MUTED, F_BOLD)
        txt(cv, str(total), PW - M - 4*mm, ty - 7*mm, 11, C_GREEN, F_BOLD, 'right')

        div_y = ty - 22*mm
        hline(cv, M, div_y, PW - 2*M, C_MUTED, 0.4)

        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, div_y - 8*mm, '04 — WELLNESS SCORE')
        hline(cv, M, div_y - 11*mm, PW - 2*M, C_GREEN, 0.7)

        w_score = d['wellness']
        gauge_ir = wellness_gauge(w_score, max_s=25)
        g_y = div_y - 62*mm
        cv.drawImage(gauge_ir, PW/2 - 28*mm, g_y, width=56*mm, height=40*mm)

        scale_y = g_y - 18*mm
        labels_s = [('1–12', 'BOM', C_GREEN), ('13–18', 'MODERADO', C_WARN), ('18–25', 'RUIM', C_RED)]
        sw = (PW - 2*M - 4*mm) / 3
        for i, (rng_lbl, lbl, col) in enumerate(labels_s):
            sx = M + i*(sw + 2*mm)
            active = (i==0 and w_score <= 12) or (i==1 and 13 <= w_score <= 18) or (i==2 and w_score > 18)
            rr(cv, sx, scale_y - 14*mm, sw, 12*mm, r=2.5*mm, fc=col if active else C_CARD)
            tc = C_DARK if active else col
            txt(cv, rng_lbl, sx + sw/2, scale_y - 5*mm, 9, tc, F_BOLD, 'center')
            txt(cv, lbl, sx + sw/2, scale_y - 11*mm, 7, tc, F_BOLD, 'center')

        rr(cv, M, scale_y - 30*mm, PW - 2*M, 13*mm, r=3*mm, fc=C_MID)
        if w_score <= 12:
            zona = 'BOM'; zona_col = C_GREEN
        elif w_score <= 18:
            zona = 'MODERADO'; zona_col = C_WARN
        else:
            zona = 'RUIM'; zona_col = C_RED
        sf(cv, zona_col); cv.setFont(F_BOLD, 8)
        cv.drawString(M + 4*mm, scale_y - 22*mm, f'ZONA {zona}:')
        sf(cv, C_WHITE); cv.setFont(F_REG, 8)
        cv.drawString(M + 36*mm, scale_y - 22*mm, 'Score mensal baseado em sono, humor, fadiga, estresse e dor muscular')
        footer(cv, '3')

    def page_readiness():
        bg(cv); top_bar(cv)
        draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm, alpha=0.06)

        def make_chart(vals, prev, color):
            labels = ['S1','S2','S3','S4']
            fig, ax = plt.subplots(figsize=(5, 3.2))
            fig.patch.set_facecolor('#0E120E')
            ax.set_facecolor('#0E120E')
            bars = ax.bar(labels, vals, color=color, width=0.5, edgecolor='none', zorder=3)
            if prev:
                ax.axhline(prev, color='#506050', linewidth=1.5, linestyle='--', zorder=2)
            mn = min(min(vals), prev or min(vals))
            mx = max(max(vals), prev or max(vals))
            rng = mx - mn or 1
            for bar, v in zip(bars, vals):
                ax.text(bar.get_x()+bar.get_width()/2, v + rng*0.05,
                        str(v), ha='center', va='bottom', color='white', fontsize=11, fontweight='bold')
            ax.set_ylim(mn*0.9, mx*1.18)
            ax.tick_params(axis='x', colors='#82A082', labelsize=11, length=0)
            ax.tick_params(axis='y', left=False, labelleft=False)
            for sp in ax.spines.values(): sp.set_visible(False)
            ax.grid(axis='y', color='#1A2A1A', linewidth=0.6, zorder=0)
            ibuf = io.BytesIO()
            fig.savefig(ibuf, dpi=120, facecolor='#0E120E', bbox_inches='tight', pad_inches=0.1, format='png')
            plt.close()
            ibuf.seek(0)
            return ImageReader(ibuf)

        cmj_vals = [v for v in d['cmj'] if v is not None]
        hrv_vals = [v for v in d['hrv'] if v is not None]
        cmj_prev = d.get('cmjAnterior')
        hrv_prev = d.get('hrvAnterior')

        # pad to 4
        while len(cmj_vals) < 4: cmj_vals.append(cmj_vals[-1] if cmj_vals else 0)
        while len(hrv_vals) < 4: hrv_vals.append(hrv_vals[-1] if hrv_vals else 0)

        cmj_avg  = sum(cmj_vals)/len(cmj_vals)
        hrv_avg  = sum(hrv_vals)/len(hrv_vals)
        diff_cmj = ((cmj_avg - cmj_prev)/cmj_prev*100) if cmj_prev else None
        diff_hrv = ((hrv_avg - hrv_prev)/hrv_prev*100) if hrv_prev else None
        diff_col_cmj = C_GREEN if (diff_cmj or 0) >= 0 else C_RED
        diff_col_hrv = C_GREEN if (diff_hrv or 0) >= 0 else C_RED

        cmj_ir = make_chart(cmj_vals, cmj_prev, '#2EC471')
        hrv_ir = make_chart(hrv_vals, hrv_prev, '#46C4A8')

        y = PH - 22*mm

        # CMJ
        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y, '05 — PRONTIDÃO NEUROMUSCULAR (CMJ)')
        hline(cv, M, y - 3, PW - 2*M, C_GREEN, 0.7)
        stats_cmj = f'Média {d["mes"]}/{d["ano"]}: {cmj_avg:.1f} cm'
        if diff_cmj is not None:
            stats_cmj += f'  ·  {d["mesAnterior"]}: {cmj_prev} cm  ·  {"+" if diff_cmj>=0 else ""}{diff_cmj:.1f}%'
        txt(cv, stats_cmj, M, y - 10*mm, 8, C_MUTED, F_REG)
        cv.drawImage(cmj_ir, M + 10*mm, y - 68*mm, width=PW - 4*M, height=54*mm)

        # HRV
        y2 = y - 84*mm
        sf(cv, C_GREEN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y2, '06 — VARIABILIDADE DA FREQUÊNCIA CARDÍACA (HRV)')
        hline(cv, M, y2 - 3, PW - 2*M, C_GREEN, 0.7)
        stats_hrv = f'Média {d["mes"]}/{d["ano"]}: {hrv_avg:.1f} ms'
        if diff_hrv is not None:
            stats_hrv += f'  ·  {d["mesAnterior"]}: {hrv_prev} ms  ·  {"+" if diff_hrv>=0 else ""}{diff_hrv:.1f}%'
        txt(cv, stats_hrv, M, y2 - 10*mm, 8, C_MUTED, F_REG)
        cv.drawImage(hrv_ir, M + 10*mm, y2 - 68*mm, width=PW - 4*M, height=54*mm)

        # VOLT INSIGHTS
        insight_y = y2 - 76*mm
        sf(cv, C_GREEN); cv.setFont(F_BOLD, 10)
        cv.drawString(M, insight_y, 'VOLT INSIGHTS')
        hline(cv, M, insight_y - 2, PW - 2*M, C_GREEN, 0.5)

        insights = []
        if cmj_vals[-1] < (cmj_prev or cmj_avg):
            insights.append(f'CMJ: queda na S4 ({cmj_vals[-1]} cm) — possível acúmulo de fadiga ao final do mês.')
        elif cmj_avg > (cmj_prev or 0):
            insights.append(f'CMJ: média mensal ({cmj_avg:.1f} cm) superior ao mês anterior — boa resposta neuromuscular.')
        if max(cmj_vals) - min(cmj_vals) > 3:
            insights.append(f'CMJ: variação de {max(cmj_vals)-min(cmj_vals):.1f} cm entre semanas — oscilação relevante para o planejamento de cargas.')
        if hrv_vals[-1] < (hrv_prev or hrv_avg):
            insights.append(f'HRV: queda na S4 ({hrv_vals[-1]} ms) — sinal de estresse acumulado ou recuperação insuficiente.')
        elif hrv_avg > (hrv_prev or 0):
            insights.append(f'HRV: média mensal ({hrv_avg:.1f} ms) acima do mês anterior — sistema nervoso autônomo respondendo bem.')
        if max(hrv_vals) - min(hrv_vals) > 30:
            insights.append(f'HRV: amplitude de {max(hrv_vals)-min(hrv_vals)} ms entre semanas — variabilidade elevada, períodos de maior e menor estresse fisiológico.')

        iy = insight_y - 8*mm
        for insight in insights:
            rr(cv, M, iy - 10*mm, PW - 2*M, 10*mm, r=2*mm, fc=C_MID)
            sf(cv, C_GREEN); cv.setFont(F_BOLD, 7)
            cv.drawString(M + 3*mm, iy - 4*mm, '▸')
            sf(cv, C_WHITE); cv.setFont(F_REG, 7.5)
            max_w = PW - 2*M - 10*mm
            display = insight
            while cv.stringWidth(display, F_REG, 7.5) > max_w and len(display) > 10:
                display = display[:-4] + '...'
            cv.drawString(M + 7*mm, iy - 4*mm, display)
            iy -= 13*mm

        footer(cv, '4')

    def page_alertas():
        bg(cv); top_bar(cv)
        draw_icon_bg(cv, PW - 36*mm, PH - 50*mm, 32*mm, alpha=0.06)
        y = PH - 22*mm

        # PONTOS DE ATENÇÃO
        sf(cv, C_WARN); cv.setFont(F_BOLD, 13)
        cv.drawString(M, y, '07 — PONTOS DE ATENÇÃO')
        hline(cv, M, y - 3, PW - 2*M, C_WARN, 0.7)

        pontos = d['pontosAtencao']
        if pontos:
            lines = [l.strip() for l in pontos.split('\n') if l.strip()]
            for i, line in enumerate(lines[:3]):
                ly = y - 22*mm - i*30*mm
                rr(cv, M, ly - 24*mm, PW - 2*M, 22*mm, fc=C_CARD)
                sf(cv, C_WARN); cv.roundRect(M, ly - 24*mm, 2.5*mm, 22*mm, 1.5*mm, fill=1, stroke=0)
                rr(cv, M + 6*mm, ly - 14*mm, 8*mm, 8*mm, r=4*mm, fc=C_WARN)
                txt(cv, '!', M + 10*mm, ly - 9.5*mm, 8, C_DARK, F_BOLD, 'center')
                txt(cv, line, M + 18*mm, ly - 10*mm, 9, C_WHITE, F_REG)
        else:
            rr(cv, M, y - 30*mm, PW - 2*M, 20*mm, fc=C_CARD)
            txt(cv, 'Nenhum ponto de atenção registrado neste mês.', M + 4*mm, y - 18*mm, 9, C_MUTED, F_REG)

        # NÃO ATINGIMOS
        na_y = y - 120*mm
        sf(cv, C_RED); cv.setFont(F_BOLD, 13)
        cv.drawString(M, na_y, '08 — NÃO ATINGIMOS')
        hline(cv, M, na_y - 3, PW - 2*M, C_RED, 0.7)

        nao = d['naoAtingimos']
        if nao:
            lines = [l.strip() for l in nao.split('\n') if l.strip()]
            for i, line in enumerate(lines[:3]):
                ly = na_y - 22*mm - i*30*mm
                rr(cv, M, ly - 24*mm, PW - 2*M, 22*mm, fc=C_CARD)
                sf(cv, C_RED); cv.roundRect(M, ly - 24*mm, 2.5*mm, 22*mm, 1.5*mm, fill=1, stroke=0)
                rr(cv, M + 6*mm, ly - 14*mm, 8*mm, 8*mm, r=4*mm, fc=C_RED)
                txt(cv, 'X', M + 10*mm, ly - 9.5*mm, 8, C_WHITE, F_BOLD, 'center')
                txt(cv, line, M + 18*mm, ly - 10*mm, 9, C_WHITE, F_REG)
        else:
            rr(cv, M, na_y - 30*mm, PW - 2*M, 20*mm, fc=C_CARD)
            txt(cv, 'Todos os objetivos foram atingidos neste mês.', M + 4*mm, na_y - 18*mm, 9, C_GREEN, F_BOLD)

        footer(cv, '5')

    def page_closing():
        bg(cv, C_DARK)
        if photo_ir:
            cv.saveState()
            cv.setFillAlpha(0.2)
            cv.drawImage(photo_ir, 0, PH*0.25, width=PW, height=PH*0.75, preserveAspectRatio=False, mask='auto')
            cv.restoreState()
        sf(cv, C_DARK); cv.setFillAlpha(0.72)
        cv.rect(0, 0, PW, PH, fill=1, stroke=0)
        cv.setFillAlpha(1)
        sf(cv, C_GREEN); cv.rect(0, PH-4, PW, 4, fill=1, stroke=0)
        logo_w = 60*mm
        draw_logo(cv, PW/2 - logo_w/2, PH*0.55, w=logo_w)
        hline(cv, PW/2 - 30*mm, PH*0.52, 60*mm, C_GREEN, 1)
        txt(cv, 'CHANGE THE MIND,',    PW/2, PH*0.49, 13, C_WHITE, F_BOLD, 'center')
        txt(cv, 'CHANGE THE ATTITUDE,', PW/2, PH*0.45, 13, C_WHITE, F_BOLD, 'center')
        txt(cv, 'CHANGE THE GAME.',     PW/2, PH*0.41, 13, C_WHITE, F_BOLD, 'center')
        txt(cv, f"Próximo relatório: {d['mesProximo']} / {d['ano']}", PW/2, PH*0.37, 9, C_MUTED, F_REG, 'center')
        draw_icon_bg(cv, PW/2 - 18*mm, PH*0.14, 36*mm, alpha=0.12)
        txt(cv, '@voltsportsscience',      PW/2, 28*mm, 9, C_MUTED, F_REG, 'center')
        txt(cv, 'volt@voltsportscience.com', PW/2, 20*mm, 8.5, C_MUTED, F_REG, 'center')

    # ── BUILD PAGES ──
    page_cover();    cv.showPage()
    page_jogos();    cv.showPage()
    page_atividades(); cv.showPage()
    page_readiness(); cv.showPage()
    page_alertas();  cv.showPage()
    page_closing();  cv.showPage()

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
