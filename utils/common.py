COUNTRY_FLAGS: dict[str, str] = {
    "angola": ":flag_ao:",
    "argentina": ":flag_ar:",
    "australia": ":flag_au:",
    "austria": ":flag_at:",
    "azerbaijan": ":flag_az:",
    "belarus": ":flag_by:",
    "belgium": ":flag_be:",
    "bolivia": ":flag_bo:",
    "brazil": ":flag_br:",
    "canada": ":flag_ca:",
    "chile": ":flag_cl:",
    "colombia": ":flag_co:",
    "croatia": ":flag_hr:",
    "east timor": ":flag_tl:",
    "egypt": ":flag_eg:",
    "estonia": ":flag_ee:",
    "ethiopia": ":flag_et:",
    "finland": ":flag_fi:",
    "france": ":flag_fr:",
    "germany": ":flag_de:",
    "greece": ":flag_gr:",
    "hungary": ":flag_hu:",
    "india": ":flag_in:",
    "iraq": ":flag_iq:",
    "ireland": ":flag_ie:",
    "israel": ":flag_il:",
    "italy": ":flag_it:",
    "japan": ":flag_jp:",
    "kenya": ":flag_ke:",
    "latvia": ":flag_lv:",
    "lesotho": ":flag_ls:",
    "lithuania": ":flag_lt:",
    "malaysia": ":flag_my:",
    "mexico": ":flag_mx:",
    "netherlands": ":flag_nl:",
    "palestine": ":flag_ps:",
    "paraguay": ":flag_py:",
    "peru": ":flag_pe:",
    "philippines": ":flag_ph:",
    "poland": ":flag_pl:",
    "portugal": ":flag_pt:",
    "romania": ":flag_ro:",
    "russia": ":flag_ru:",
    "saudi arabia": ":flag_sa:",
    "serbia": ":flag_rs:",
    "south africa": ":flag_za:",
    "spain": ":flag_es:",
    "sweden": ":flag_se:",
    "switzerland": ":flag_ch:",
    "taiwan": ":flag_tw:",
    "tunisia": ":flag_tn:",
    "turkey": ":flag_tr:",
    "ukraine": ":flag_ua:",
    "united kingdom": ":flag_gb:",
    "united korea": ":flag_kr:",
    "united states": ":flag_us:",
    "uruguay": ":flag_uy:",
    "vatican": ":flag_va:",
    "venezuela": ":flag_ve:",
}


def country_flag(country_name: str | None) -> str | None:
    if not country_name:
        return None
    return COUNTRY_FLAGS.get(str(country_name).strip().casefold())


def country_with_flag(country_name: str | None, left: bool) -> str:
    name = str(country_name or "unknown")
    flag = country_flag(name)
    if not flag:
        return name
    if left:
        return f"{flag} {name}"
    else:
        return f"{name} {flag}"
