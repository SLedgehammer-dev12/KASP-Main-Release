/**
 * KASP Thermodynamics Handbook & Engineering Reference Modal (handbookModal.js)
 * Full bilingual (TR/EN) guide matching desktop ThermodynamicsHandbookDialog.
 */

import { icon } from "../../vendor/icons.js";
import { closeModal } from "../store/uiStore.js";

export function renderHandbookModal(container) {
  let activeTab = "tr"; // "tr" | "en"

  function render() {
    container.innerHTML = `
      <div class="modal-backdrop" id="handbook-modal-backdrop">
        <div class="modal-dialog modal-lg" style="height: 85vh; max-height: 90vh;">
          
          <!-- Modal Header -->
          <div class="modal-header">
            <div style="display: flex; align-items: center; gap: 10px;">
              ${icon("book", 20, "text-primary")}
              <div>
                <h3 style="margin: 0; font-size: 15px; font-weight: 700;">KASP Termodinamik & Mühendislik El Kitabı</h3>
                <div style="font-size: 11px; color: var(--color-text-secondary);">Thermodynamics Handbook & Path Integration Theory</div>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="btn-group" style="display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--radius-sm); overflow: hidden;">
                <button id="btn-handbook-tr" class="btn btn-sm ${activeTab === 'tr' ? 'btn-primary' : ''}" style="border-radius: 0; padding: 4px 10px; font-size: 11px;">
                  🇹🇷 Türkçe
                </button>
                <button id="btn-handbook-en" class="btn btn-sm ${activeTab === 'en' ? 'btn-primary' : ''}" style="border-radius: 0; padding: 4px 10px; font-size: 11px;">
                  🇺🇸 English
                </button>
              </div>
              <button id="btn-close-handbook" class="btn btn-sm btn-icon" style="color: var(--color-text-secondary);">
                ${icon("x", 16)}
              </button>
            </div>
          </div>

          <!-- Modal Body (Scrollable) -->
          <div class="modal-body" style="padding: 24px 28px; line-height: 1.6; font-size: 13px;">
            ${activeTab === "tr" ? renderTurkishHandbook() : renderEnglishHandbook()}
          </div>

          <!-- Modal Footer -->
          <div class="modal-footer" style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 11px; color: var(--color-text-secondary);">
              KASP v4.1 • ISO 5389 & ASME PTC-10 & API 617 Uyumlu
            </div>
            <button id="btn-footer-close-handbook" class="btn btn-sm btn-secondary">Kapat</button>
          </div>

        </div>
      </div>
    `;

    // Event Bindings
    container.querySelector("#btn-close-handbook")?.addEventListener("click", closeModal);
    container.querySelector("#btn-footer-close-handbook")?.addEventListener("click", closeModal);
    container.querySelector("#handbook-modal-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "handbook-modal-backdrop") closeModal();
    });

    container.querySelector("#btn-handbook-tr")?.addEventListener("click", () => {
      activeTab = "tr";
      render();
    });

    container.querySelector("#btn-handbook-en")?.addEventListener("click", () => {
      activeTab = "en";
      render();
    });
  }

  render();
}

function renderTurkishHandbook() {
  return `
    <article class="handbook-content">
      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 0;">
        1. Durum-Seviyesi EoS Çözücüler (State Model)
      </h2>
      <p>
        KASP, santrifüj kompresör hesaplamalarında gaz karışımının termodinamik durumunu (P, T, v, h, s, Z, C_p, C_v) 
        belirlemek için endüstri standardı durum denklemlerini (Equation of State - EoS) kullanır:
      </p>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
        <div class="card" style="padding: 12px; border-left: 3px solid var(--color-primary);">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: var(--color-primary);">Peng-Robinson (PR & PR78)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Doğal gaz iletimi, hidrokarbon karışımları ve petrol/gaz tesislerinde dünya standardıdır. 
            Sıvı yoğunluğu ve kritik nokta civarında yüksek doğruluk sağlar. İkili etkileşim katsayıları (k_ij) ile tam uyumludur.
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #0ea5e9;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #0ea5e9;">Soave-Redlich-Kwong (SRK)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Rafineri gazları, hidrojen zengin akımlar ve petrokimya proseslerinde yaygın kullanılır. 
            Hafif gazlar ve polar olmayan karışımlar için Peng-Robinson ile benzer, ancak entalpi türevlerinde farklı davranış gösterir.
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #8b5cf6;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #8b5cf6;">Lee-Kesler-Pitzer (LKP)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Karşılıklı durumlar ilkesine (Principle of Corresponding States) dayalı 3-parametreli referans akışkan modelidir. 
            Kritik basıncın çok üzerindeki süperkritik gaz kompresörlerinde hacimsel doğruluk sağlar.
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #10b981;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #10b981;">CoolProp HEOS (Helmholtz EoS)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Saf akışkanlar ve standart hava/azot/karbondioksit için NIST REFPROP düzeyinde yüksek hassasiyetli Helmholtz serbest enerjisi formülasyonu uygular.
          </p>
        </div>
      </div>

      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 24px;">
        2. Mühendislik Karar Matrisi: Hangi Şartta Hangi EoS Seçilmeli?
      </h2>
      <table class="kasp-table" style="font-size: 12px; margin-bottom: 20px;">
        <thead>
          <tr>
            <th>Proses Akımı / Şartlar</th>
            <th>Önerilen Birincil EoS</th>
            <th>Alternatif / Doğrulama EoS</th>
            <th>Açıklama</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Doğal Gaz İletim Boru Hattı</b> (15-90 bar)</td>
            <td><span class="badge badge-success">Peng-Robinson (PR)</span></td>
            <td>SRK / LKP</td>
            <td>Metan ağırlıklı karışımlarda en tutarlı Z ve C_p/C_v profilini sunar.</td>
          </tr>
          <tr>
            <td><b>Sentez Gazı (H2 + CO + CO2)</b></td>
            <td><span class="badge badge-success">SRK</span></td>
            <td>PR</td>
            <td>Hafif gazlarda ve hidrojen penetrasyonlu karışımlarda tercih edilir.</td>
          </tr>
          <tr>
            <td><b>Süperkritik CO2 (sCO2)</b></td>
            <td><span class="badge badge-success">CoolProp HEOS</span></td>
            <td>Lee-Kesler (LKP)</td>
            <td>Kritik nokta civarındaki dik yoğunluk gradyanını doğru yakalar.</td>
          </tr>
          <tr>
            <td><b>Islak Gaz & C3+ Ağır Hidrokarbon</b></td>
            <td><span class="badge badge-success">Peng-Robinson (PR78)</span></td>
            <td>SRK + kij override</td>
            <td>k_ij etkileşim matrisiyle yoğuşma riski ve aşırı faz sınırları tespit edilir.</td>
          </tr>
        </tbody>
      </table>

      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 24px;">
        3. Sıkıştırma Yolu Yöntemleri (Path Sizing)
      </h2>
      <p>
        Santrifüj kompresörde gazın giriş (1) durumundan çıkış (2) durumuna ulaşması sırasındaki politropik yol entegrasyonu:
      </p>

      <div style="background: var(--color-surface); padding: 14px; border-radius: var(--radius-md); font-family: var(--font-mono); font-size: 12px; margin-bottom: 14px;">
        H_p = ∫ v dP = [ Z_avg · R · T_1 / (M · (n-1)/n) ] · [ (P_2 / P_1)^((n-1)/n) - 1 ]
      </div>

      <ul style="padding-left: 20px; font-size: 12px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 8px;">
        <li><b>Schultz Yöntemi:</b> Politropik basma yüksekliği için gerçek gaz düzeltme faktörü f_T ve politropik üs n_p kullanır (ASME PTC-10 standardının temelidir).</li>
        <li><b>Huntington Yöntemi:</b> Değişken sıkıştırılabilirlik faktörü Z ve katsayı gradyanlarını integre ederek yüksek basınç oranlarında Schultz'dan daha kararlı sonuçlar üretir.</li>
        <li><b>ASME PTC-10 Prosedürü:</b> Saha testlerinde garanti edilen nokta ile test akışkanı arasındaki benzerlik parametrelerini (Re oranı, hacim oranı, akış katsayısı) denetler.</li>
        <li><b>Rigorous Integral:</b> Basınç aralığını çok sayıda mikro basamağa (N=50-200) bölerek her adımda gerçek termodinamik durum integrali alır.</li>
      </ul>

      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 24px;">
        4. API 617 Tasarım ve Mekanik Limitler
      </h2>
      <p style="font-size: 12px; color: var(--color-text-secondary);">
        API 617 Standardı (Axial and Centrifugal Compressors and Expander-compressors for Petroleum, Chemical and Gas Industry Services):
      </p>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
        <div class="card" style="padding: 10px; text-align: center;">
          <div style="font-size: 11px; color: var(--color-text-secondary);">Giriş Mach Sayısı (M_1)</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--color-primary); margin-top: 4px;">&lt; 0.85</div>
          <div style="font-size: 10px; color: var(--color-text-secondary);">Şok dalgası önleme sınırı</div>
        </div>
        <div class="card" style="padding: 10px; text-align: center;">
          <div style="font-size: 11px; color: var(--color-text-secondary);">Akış Katsayısı (φ)</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--color-success); margin-top: 4px;">0.015 - 0.150</div>
          <div style="font-size: 10px; color: var(--color-text-secondary);">Optimum çark verim aralığı</div>
        </div>
        <div class="card" style="padding: 10px; text-align: center;">
          <div style="font-size: 11px; color: var(--color-text-secondary);">Maks. Çevre Hızı (U_tip)</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--color-warning); margin-top: 4px;">&lt; 320 m/s</div>
          <div style="font-size: 10px; color: var(--color-text-secondary);">Mekanik gerilme emniyeti</div>
        </div>
      </div>
    </article>
  `;
}

function renderEnglishHandbook() {
  return `
    <article class="handbook-content">
      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 0;">
        1. Equation of State (EoS) Engines
      </h2>
      <p>
        KASP utilizes industry-standard Equations of State to evaluate complete thermodynamic state trajectories 
        (P, T, v, h, s, Z, C_p, C_v) across centrifugal compressor compression stages:
      </p>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
        <div class="card" style="padding: 12px; border-left: 3px solid var(--color-primary);">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: var(--color-primary);">Peng-Robinson (PR & PR78)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Global benchmark for natural gas pipeline transmission and oil & gas facilities. 
            Provides superior liquid-density accuracy and near-critical envelope tracking with binary interaction parameters (k_ij).
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #0ea5e9;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #0ea5e9;">Soave-Redlich-Kwong (SRK)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Standard in petrochemicals, syngas (H2/CO), and refinery processing. Robust across non-polar gas mixtures.
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #8b5cf6;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #8b5cf6;">Lee-Kesler-Pitzer (LKP)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            Extended Corresponding States 3-parameter model with reference fluid equations. Highly accurate for supercritical high-pressure applications.
          </p>
        </div>

        <div class="card" style="padding: 12px; border-left: 3px solid #10b981;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; color: #10b981;">CoolProp HEOS (Helmholtz EoS)</h4>
          <p style="margin: 0; font-size: 12px; color: var(--color-text-secondary);">
            NIST REFPROP-grade multi-parameter Helmholtz free energy equations for pure gases, Air, Nitrogen, and Carbon Dioxide.
          </p>
        </div>
      </div>

      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 24px;">
        2. Engineering Decision Matrix: Which EoS to Choose?
      </h2>
      <table class="kasp-table" style="font-size: 12px; margin-bottom: 20px;">
        <thead>
          <tr>
            <th>Gas Service / Operating Envelope</th>
            <th>Primary Recommended EoS</th>
            <th>Alternative / Cross-Check</th>
            <th>Key Rationale</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Natural Gas Transmission</b> (15-90 bar)</td>
            <td><span class="badge badge-success">Peng-Robinson (PR)</span></td>
            <td>SRK / LKP</td>
            <td>Most consistent Z-factor and specific heat ratio k profiles.</td>
          </tr>
          <tr>
            <td><b>Synthesis Gas (H2 + CO + CO2)</b></td>
            <td><span class="badge badge-success">SRK</span></td>
            <td>PR</td>
            <td>Preferred for light gas hydrogen diffusion mixtures.</td>
          </tr>
          <tr>
            <td><b>Supercritical CO2 (sCO2)</b></td>
            <td><span class="badge badge-success">CoolProp HEOS</span></td>
            <td>Lee-Kesler (LKP)</td>
            <td>Captures steep density and isobaric heat capacity peaks near critical point.</td>
          </tr>
          <tr>
            <td><b>Wet Hydrocarbon Gas & C3+ NGL</b></td>
            <td><span class="badge badge-success">Peng-Robinson (PR78)</span></td>
            <td>SRK with k_ij override</td>
            <td>Critical for dew point tracking and condensation envelope boundaries.</td>
          </tr>
        </tbody>
      </table>

      <h2 style="font-size: 18px; color: var(--color-primary); border-bottom: 2px solid var(--color-border); padding-bottom: 6px; margin-top: 24px;">
        3. Compression Path Sizing Methods
      </h2>
      <p>
        Evaluation of polytropic head (H_p), gas power, and temperature rise between inlet (1) and discharge (2):
      </p>

      <div style="background: var(--color-surface); padding: 14px; border-radius: var(--radius-md); font-family: var(--font-mono); font-size: 12px; margin-bottom: 14px;">
        H_p = ∫ v dP = [ Z_avg · R · T_1 / (M · (n-1)/n) ] · [ (P_2 / P_1)^((n-1)/n) - 1 ]
      </div>

      <ul style="padding-left: 20px; font-size: 12px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 8px;">
        <li><b>Schultz Method:</b> Uses polytropic volume exponent n_v and head correction factor f_T (core of ASME PTC-10 standard).</li>
        <li><b>Huntington Method:</b> Integrates point-by-point compressibility gradient; superior convergence at high pressure ratios.</li>
        <li><b>ASME PTC-10 Procedure:</b> Evaluates dimensional similitude (Reynolds number ratio, volume ratio, flow coefficient) for off-design field tests.</li>
        <li><b>Rigorous Integral:</b> Discretizes pressure differential into N=100 micro-stages for direct numerical integration.</li>
      </ul>
    </article>
  `;
}
