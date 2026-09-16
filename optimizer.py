from __future__ import annotations
from typing import Any
import math
import pulp


def optimize(
    data: dict,
    ana_sabit: bool = True,
    ana_tercih_agirligi: float = 0.7,
    hiz_agirlik: float = 0.5,
    min_destek_sicil: int = 0,
    max_destek_sicil: int = 10,
    max_destek_portfoy: int = 5,
    rol_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    uyarilar: list[str] = []
    tum_siciller: list[str] = data["tum_siciller"]
    ic_pf: list[str] = data["ic_portfoyler"]
    capacity: dict[str, float] = data["capacity"]
    demand: dict[str, float] = data["demand"]
    speed_norm: dict[str, float] = data["speed_norm"]
    eligible: set[tuple] = data["eligible"]
    ana_atama_mevcut: dict[str, str] = data["ana_atama_mevcut"]
    sicil_portfoy_sure: dict[tuple, float] = data.get("sicil_portfoy_sure", {})
    portfoy_sicil_sure: dict[str, float] = data.get("portfoy_sicil_sure", {})
    sicil_gecici_pencere: dict[str, list] = data.get("sicil_gecici_pencere", {})
    pf_ana_gecici: dict[str, list] = data.get("pf_ana_gecici", {})

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=120, gapRel=0.05)

    # ── ANA KATMANI ───────────────────────────────────────────────────────────
    if ana_sabit:
        ana_atama: dict[str, str] = dict(ana_atama_mevcut)
        durum_ana = "Mevcut atama kullanıldı"
        ana_pf_set = set(ana_atama.values())
        for pf in ic_pf:
            if pf not in ana_pf_set:
                uyarilar.append(f"Portföy '{pf}': ANA sicili yok.")
    else:
        ana_elig = [(u, p) for (u, p) in eligible if p in ic_pf]
        model_ana = pulp.LpProblem("AnaAtama", pulp.LpMaximize)
        a = {(u, p): pulp.LpVariable(f"a_{u}_{p}", cat="Binary") for (u, p) in ana_elig}
        Z_ana = pulp.LpVariable("Z_ana", lowBound=0, upBound=1)

        for u in tum_siciller:
            u_elig = [(u2, p2) for (u2, p2) in ana_elig if u2 == u]
            if u_elig:
                model_ana += pulp.lpSum(a[ud] for ud in u_elig) == 1
            else:
                uyarilar.append(f"Sicil {u}: Eligible ANA portföyü yok.")

        for pf in ic_pf:
            pf_elig = [(u2, p2) for (u2, p2) in ana_elig if p2 == pf]
            if pf_elig:
                model_ana += pulp.lpSum(a[ud] for ud in pf_elig) >= 1
                dem = demand.get(pf, 1.0)
                contrib = portfoy_sicil_sure.get(pf, 0.0)
                if dem > 0 and contrib > 0:
                    cap_sum = contrib * pulp.lpSum(a[(u2, p2)] for (u2, p2) in pf_elig)
                    model_ana += Z_ana <= cap_sum / dem

        mevcut_ana_set = {(u, p) for u, p in ana_atama_mevcut.items()}
        n_mevcut = max(len(mevcut_ana_set), 1)
        tercih_bonus = pulp.lpSum(
            a[(u, p)] for (u, p) in ana_elig if (u, p) in mevcut_ana_set
        ) / n_mevcut

        model_ana += Z_ana + ana_tercih_agirligi * tercih_bonus
        model_ana.solve(solver)
        durum_ana = pulp.LpStatus[model_ana.status]

        if model_ana.status != 1:
            return _bos_sonuc(data, uyarilar, durum_ana, "Çözülmedi")

        ana_atama = {}
        for (u, pf) in ana_elig:
            if pulp.value(a[(u, pf)]) is not None and pulp.value(a[(u, pf)]) > 0.5:
                ana_atama[u] = pf

    # ── ANA kapasite ─────────────────────────────────────────────────────────
    # N_ana × portfoy_sicil_sure = portföydeki ANA sicillerin toplam günlük katkısı
    sicil_aktif = set(tum_siciller)
    pf_ana_siciller: dict[str, list[str]] = {}
    for u, pf in ana_atama.items():
        if u in sicil_aktif:
            pf_ana_siciller.setdefault(pf, []).append(u)

    ana_kapasite: dict[str, float] = {}
    for pf in ic_pf:
        n_ana = len(pf_ana_siciller.get(pf, []))
        ana_kapasite[pf] = n_ana * portfoy_sicil_sure.get(pf, 0.0)

    ana_set: set[tuple] = {(u, pf) for u, pf in ana_atama.items()}

    # ── Sicil DESTEK kapasitesi ───────────────────────────────────────────────
    # Günlük teorik kapasite eksi ANA portföyüne katkı = DESTEK için kalan süre
    destek_available: dict[str, float] = {}
    for u in tum_siciller:
        teorik = capacity.get(u, 0.0)
        pf_ana = ana_atama.get(u)
        katki_ana = portfoy_sicil_sure.get(pf_ana, 0.0) if pf_ana else 0.0
        destek_available[u] = max(teorik - katki_ana, 0.0)

    # ── DESTEK KATMANI ────────────────────────────────────────────────────────
    # Portföy başına max DESTEK = gerçek talep açığını kapatmak için gereken sicil sayısı
    # (talep - ANA kapasitesi) / kişi başı günlük süre. Tarihsel personel sayısına değil,
    # o günkü gerçek talep-kapasite açığına dayanır.
    destek_max_pf: dict[str, int] = {}
    for pf in ic_pf:
        kisi_sure = portfoy_sicil_sure.get(pf, 0.0)
        acik = max(demand.get(pf, 0.0) - ana_kapasite.get(pf, 0.0), 0.0)
        needed = math.ceil(acik / kisi_sure) if kisi_sure > 0 else 0
        destek_max_pf[pf] = min(needed, max_destek_sicil)

    # Uygunluk: DESTEK için boş süresi olan ve ANA olmayan siciller
    destek_elig = [
        (u, pf) for (u, pf) in eligible
        if pf in ic_pf
        and (u, pf) not in ana_set
        and destek_available.get(u, 0.0) > 0
        and destek_max_pf.get(pf, 0) > 0
    ]

    if not destek_elig:
        destek_atama: set[tuple] = set()
        destek_kapasite = {pf: 0.0 for pf in ic_pf}
        coverage = _coverage(ic_pf, ana_kapasite, destek_kapasite, demand)
        return {
            "ana_atama": ana_atama, "destek_atama": destek_atama,
            "demand": demand, "ana_kapasite": ana_kapasite,
            "destek_kapasite": destek_kapasite, "coverage": coverage,
            "uyarilar": uyarilar, "durum_ana": durum_ana, "durum_destek": "Atanacak aday yok",
        }

    model_d = pulp.LpProblem("DestekAtama", pulp.LpMaximize)
    y = {(u, pf): pulp.LpVariable(f"y_{u}_{pf}", cat="Binary") for (u, pf) in destek_elig}
    # t: sicil u'nun portföy pf'e katkısı; en fazla portfoy_sicil_sure (bir sicil payı) veya destek_available
    t = {(u, pf): pulp.LpVariable(f"t_{u}_{pf}", lowBound=0) for (u, pf) in destek_elig}
    Z_d = pulp.LpVariable("Z_d", lowBound=0, upBound=1)

    for (u, pf) in destek_elig:
        avail = destek_available.get(u, 0.0)
        katki_max = min(avail, portfoy_sicil_sure.get(pf, avail))
        model_d += t[(u, pf)] <= katki_max * y[(u, pf)]

    # Sicil toplam DESTEK süresi ≤ destek_available
    for u in tum_siciller:
        u_list = [(u2, p2) for (u2, p2) in destek_elig if u2 == u]
        avail = destek_available.get(u, 0.0)
        if u_list and avail > 0:
            model_d += pulp.lpSum(t[ud] for ud in u_list) <= avail

    # Sicil başına max DESTEK portföy sayısı
    for u in tum_siciller:
        u_list = [(u2, p2) for (u2, p2) in destek_elig if u2 == u]
        if u_list:
            model_d += pulp.lpSum(y[ud] for ud in u_list) <= max_destek_portfoy

    # Portföy başına DESTEK sicil sayısı: en fazla destek_max_pf[pf]
    for pf in ic_pf:
        pf_list = [(u2, p2) for (u2, p2) in destek_elig if p2 == pf]
        if not pf_list:
            continue
        eff_max = min(destek_max_pf[pf], len(pf_list))
        model_d += pulp.lpSum(y[ud] for ud in pf_list) <= eff_max
        if min_destek_sicil > 0 and destek_max_pf[pf] > 0:
            eff_min = min(min_destek_sicil, len(pf_list))
            model_d += pulp.lpSum(y[ud] for ud in pf_list) >= eff_min

    # Kapsama: (ANA + DESTEK t toplamı) / talep ≥ Z_d
    for pf in ic_pf:
        pf_list = [(u2, p2) for (u2, p2) in destek_elig if p2 == pf]
        dem = demand.get(pf, 1.0)
        if dem > 0:
            toplam_kap = ana_kapasite.get(pf, 0.0) + (
                pulp.lpSum(t[ud] for ud in pf_list) if pf_list else 0
            )
            model_d += Z_d <= toplam_kap / dem

    # Hız dengesi
    speeds = sorted(speed_norm.values())
    medyan_hiz = speeds[len(speeds) // 2] if speeds else 0.5
    hizli = {u for u, s in speed_norm.items() if s >= medyan_hiz}
    fark_pos = {pf: pulp.LpVariable(f"fark_pos_{pf}", lowBound=0) for pf in ic_pf}
    fark_neg = {pf: pulp.LpVariable(f"fark_neg_{pf}", lowBound=0) for pf in ic_pf}
    for pf in ic_pf:
        pf_list = [(u2, p2) for (u2, p2) in destek_elig if p2 == pf]
        if pf_list:
            n_hizli = pulp.lpSum(y[(u2, p2)] for (u2, p2) in pf_list if u2 in hizli)
            n_yavas = pulp.lpSum(y[(u2, p2)] for (u2, p2) in pf_list if u2 not in hizli)
            model_d += fark_pos[pf] >= n_hizli - n_yavas
            model_d += fark_neg[pf] >= n_yavas - n_hizli
    n_pf = max(len(ic_pf), 1)
    hiz_dengesi_penalty = pulp.lpSum(fark_pos[pf] + fark_neg[pf] for pf in ic_pf) / n_pf

    # GECİCİ çakışma penaltisi
    def _cakisma_dk(p1, p2):
        return sum(max(0, min(a_bit, b_bit) - max(a_bas, b_bas)) for a_bas, a_bit in p1 for b_bas, b_bit in p2)

    gecici_ceza_katsayi: dict[tuple, float] = {}
    for (u, pf) in destek_elig:
        u_pencere = sicil_gecici_pencere.get(u, [])
        pf_pencere = pf_ana_gecici.get(pf, [])
        if u_pencere and pf_pencere:
            cakisma = _cakisma_dk(u_pencere, pf_pencere)
            toplam_ana = sum(bit - bas for bas, bit in pf_pencere)
            gecici_ceza_katsayi[(u, pf)] = cakisma / max(toplam_ana, 1)
        else:
            gecici_ceza_katsayi[(u, pf)] = 0.0

    n_elig = max(len(destek_elig), 1)
    gecici_ceza = (0.001 / n_elig) * pulp.lpSum(
        gecici_ceza_katsayi[(u, pf)] * y[(u, pf)] for (u, pf) in destek_elig
    )

    # Admin siciller DESTEK'te son tercih
    if rol_map:
        admin_elig_list = [(u, pf) for (u, pf) in destek_elig if rol_map.get(u) == "8991"]
        if admin_elig_list:
            n_norm = max(len(admin_elig_list), 1)
            admin_ceza = (0.01 / n_norm) * pulp.lpSum(y[ud] for ud in admin_elig_list)
        else:
            admin_ceza = 0
    else:
        admin_ceza = 0

    model_d += hiz_agirlik * Z_d - (1 - hiz_agirlik) * hiz_dengesi_penalty - admin_ceza - gecici_ceza
    model_d.solve(solver)
    durum_destek = pulp.LpStatus[model_d.status]

    destek_atama = set()
    destek_kapasite: dict[str, float] = {pf: 0.0 for pf in ic_pf}
    if model_d.status == 1:
        for (u, pf) in destek_elig:
            if pulp.value(y[(u, pf)]) is not None and pulp.value(y[(u, pf)]) > 0.5:
                destek_atama.add((u, pf))
            t_val = pulp.value(t[(u, pf)])
            if t_val is not None and t_val > 0:
                destek_kapasite[pf] += t_val
    else:
        uyarilar.append(f"DESTEK optimizasyonu: {durum_destek}. Parametreleri kontrol edin.")

    coverage = _coverage(ic_pf, ana_kapasite, destek_kapasite, demand)

    return {
        "ana_atama": ana_atama,
        "destek_atama": destek_atama,
        "demand": demand,
        "ana_kapasite": ana_kapasite,
        "destek_kapasite": destek_kapasite,
        "coverage": coverage,
        "uyarilar": uyarilar,
        "durum_ana": durum_ana,
        "durum_destek": durum_destek,
    }


def _coverage(ic_pf, ana_kap, destek_kap, demand):
    return {
        pf: (ana_kap.get(pf, 0) + destek_kap.get(pf, 0)) / demand.get(pf, 1.0)
        if demand.get(pf, 0) > 0 else 1.0
        for pf in ic_pf
    }


def _bos_sonuc(data, uyarilar, durum_ana, durum_destek):
    ic_pf = data["ic_portfoyler"]
    return {
        "ana_atama": {}, "destek_atama": set(),
        "demand": data["demand"],
        "ana_kapasite": {pf: 0.0 for pf in ic_pf},
        "destek_kapasite": {pf: 0.0 for pf in ic_pf},
        "coverage": {pf: 0.0 for pf in ic_pf},
        "uyarilar": uyarilar,
        "durum_ana": durum_ana,
        "durum_destek": durum_destek,
    }
