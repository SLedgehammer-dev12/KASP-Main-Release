"""3-Katmanlı Termodinamik Mimari SVG diyagram üreticisi."""

from release_metadata import APP_VERSION


def generate_3layer_diagram_svg(theme: dict) -> str:
    """Tema renklerine göre SVG string'i oluşturur."""
    bg = theme.get("background", "#1F1F1F")
    fg = theme.get("text", "#CCCCCC")
    primary = theme.get("primary", "#0078D4")
    surface = theme.get("surface", "#181818")
    border = theme.get("border", "#334155")
    warning = theme.get("warning", "#F59E0B")
    success = theme.get("success", "#10B981")
    danger = theme.get("danger", "#EF4444")

    # Derived colors
    text_sec = theme.get("text_secondary", "#888888")
    node_fill = surface
    line_color = border
    group_fill = bg
    group_hdr = theme.get("surface", surface)

    w, h = 720, 520
    mx, layer_h = 20, 110
    l1_y, l2_y, l3_y = 60, 240, 420
    layer_w = w - 2 * mx

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs>
  <marker id="arrow" markerWidth="8" markerHeight="5" refX="7" refY="2.5" orient="auto">
    <polygon points="0 0, 8 2.5, 0 5" fill="{primary}" />
  </marker>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Inter, sans-serif; font-size: 11px; fill: {fg}; }}
  text.title {{ font-size: 12px; font-weight: 600; fill: {text_sec}; }}
  text.big {{ font-size: 13px; font-weight: 500; fill: {fg}; }}
</style>
<rect x="0" y="0" width="{w}" height="{h}" fill="{bg}" rx="4" />

<!-- === KATMAN 1 === -->
<rect x="{mx}" y="{l1_y}" width="{layer_w}" height="{layer_h}" fill="none" stroke="{primary}" stroke-width="1.5" rx="6" />
<rect x="{mx}" y="{l1_y}" width="{layer_w}" height="24" fill="{primary}" rx="6" />
<rect x="{mx}" y="{l1_y + 18}" width="{layer_w}" height="6" fill="{primary}" />
<text x="{mx + 10}" y="{l1_y + 17}" class="title" fill="#fff">Katman 1: EoS Durum Modeli (State Model)</text>

<!-- EOS düğümleri -->
<rect x="40" y="{l1_y + 40}" width="100" height="30" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="90" y="{l1_y + 60}" text-anchor="middle" class="big">CoolProp HEOS</text>

<rect x="160" y="{l1_y + 40}" width="115" height="30" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="217" y="{l1_y + 60}" text-anchor="middle" class="big">thermopack</text>

<rect x="295" y="{l1_y + 40}" width="105" height="30" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="347" y="{l1_y + 60}" text-anchor="middle" class="big">PR / SRK</text>

<rect x="420" y="{l1_y + 40}" width="75" height="30" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="457" y="{l1_y + 60}" text-anchor="middle" class="big">AGA8</text>

<rect x="515" y="{l1_y + 40}" width="60" height="30" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="545" y="{l1_y + 60}" text-anchor="middle" class="big">ccp</text>

<rect x="595" y="{l1_y + 40}" width="90" height="30" fill="{node_fill}" stroke="{success}" stroke-width="1.5" rx="4" />
<text x="640" y="{l1_y + 45}" text-anchor="middle" class="title" fill="{success}">DWSIM</text>
<text x="640" y="{l1_y + 60}" text-anchor="middle" class="title" fill="{success}">[YENİ]</text>

<!-- Katman 1 → 2 okları -->
<line x1="90" y1="{l1_y + 70}" x2="90" y2="{l2_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="217" y1="{l1_y + 70}" x2="217" y2="{l2_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="347" y1="{l1_y + 70}" x2="347" y2="{l2_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="457" y1="{l1_y + 70}" x2="457" y2="{l2_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="545" y1="{l1_y + 70}" x2="545" y2="{l2_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="640" y1="{l1_y + 70}" x2="640" y2="{l2_y}" stroke="{success}" stroke-width="1.2" marker-end="url(#arrow)" />

<!-- Veri akışı etiketi -->
<rect x="130" y="{l1_y + l2_y - 10 //2}" width="210" height="18" fill="{bg}" stroke="{border}" stroke-width="0.5" rx="3" />
<text x="235" y="{l1_y + (l2_y - l1_y) // 2 + 4}" text-anchor="middle" font-size="9" fill="{text_sec}">P, T, X → Z, H, S, Cp, Cv, k</text>

<!-- === KATMAN 2 === -->
<rect x="{mx}" y="{l2_y}" width="{layer_w}" height="{layer_h}" fill="none" stroke="{warning}" stroke-width="1.5" rx="6" />
<rect x="{mx}" y="{l2_y}" width="{layer_w}" height="24" fill="{warning}" rx="6" />
<rect x="{mx}" y="{l2_y + 18}" width="{layer_w}" height="6" fill="{warning}" />
<text x="{mx + 10}" y="{l2_y + 17}" class="title" fill="#000">Katman 2: Kök Çözücü (State Solver)</text>

<!-- Solver düğümleri -->
<rect x="60" y="{l2_y + 40}" width="125" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="122" y="{l2_y + 57}" text-anchor="middle" class="big">AJ-NR</text>
<text x="122" y="{l2_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Analitik Jakobiyen</text>

<rect x="205" y="{l2_y + 40}" width="125" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="267" y="{l2_y + 57}" text-anchor="middle" class="big">FD-NR</text>
<text x="267" y="{l2_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Sonlu Farklar</text>

<rect x="350" y="{l2_y + 40}" width="130" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="415" y="{l2_y + 57}" text-anchor="middle" class="big">Brent Hibrit</text>
<text x="415" y="{l2_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Bisection + Sekant</text>

<rect x="500" y="{l2_y + 40}" width="135" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="567" y="{l2_y + 57}" text-anchor="middle" class="big">Auto Benchmark</text>
<text x="567" y="{l2_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Dinamik Seçim</text>

<!-- Katman 2 → 3 okları -->
<line x1="122" y1="{l2_y + 80}" x2="122" y2="{l3_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="267" y1="{l2_y + 80}" x2="267" y2="{l3_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="415" y1="{l2_y + 80}" x2="415" y2="{l3_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />
<line x1="567" y1="{l2_y + 80}" x2="567" y2="{l3_y}" stroke="{line_color}" stroke-width="1" marker-end="url(#arrow)" />

<rect x="380" y="{l2_y + l3_y - 10 //2}" width="180" height="18" fill="{bg}" stroke="{border}" stroke-width="0.5" rx="3" />
<text x="470" y="{l2_y + (l3_y - l2_y) // 2 + 4}" text-anchor="middle" font-size="9" fill="{text_sec}">T_isen, H_isen</text>

<!-- === KATMAN 3 === -->
<rect x="{mx}" y="{l3_y}" width="{layer_w}" height="{layer_h}" fill="none" stroke="{danger}" stroke-width="1.5" rx="6" />
<rect x="{mx}" y="{l3_y}" width="{layer_w}" height="24" fill="{danger}" rx="6" />
<rect x="{mx}" y="{l3_y + 18}" width="{layer_w}" height="6" fill="{danger}" />
<text x="{mx + 10}" y="{l3_y + 17}" class="title" fill="#fff">Katman 3: Sıkıştırma Yolu (Sizing Path)</text>

<!-- Metot düğümleri -->
<rect x="40" y="{l3_y + 40}" width="165" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="122" y="{l3_y + 57}" text-anchor="middle" class="big">Metot 1</text>
<text x="122" y="{l3_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Ort. Özellikler (API 617)</text>

<rect x="220" y="{l3_y + 40}" width="155" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="297" y="{l3_y + 57}" text-anchor="middle" class="big">Metot 2</text>
<text x="297" y="{l3_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Uç Nokta Yöntemi</text>

<rect x="390" y="{l3_y + 40}" width="145" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="462" y="{l3_y + 57}" text-anchor="middle" class="big">Metot 3</text>
<text x="462" y="{l3_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Artımlı Entegrasyon</text>

<rect x="550" y="{l3_y + 40}" width="153" height="40" fill="{node_fill}" stroke="{border}" stroke-width="1" rx="4" />
<text x="626" y="{l3_y + 57}" text-anchor="middle" class="big">Metot 4</text>
<text x="626" y="{l3_y + 72}" text-anchor="middle" font-size="9" fill="{text_sec}">Direct H-S (Mollier)</text>

<!-- Alt bilgi -->
<text x="{w // 2}" y="{h - 8}" text-anchor="middle" font-size="9" fill="{text_sec}">KASP v{APP_VERSION} — 3-Katmanlı Termodinamik Mimari</text>

</svg>'''
    return svg
