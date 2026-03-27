def get_wpt_price(total_mined):
    # Prix de base : 0.0001$
    # On ajoute 0.00001$ tous les 1 million de tokens minés
    base_price = 0.0001
    growth_factor = total_mined / 1000000 * 0.00001
    return round(base_price + growth_factor, 6)
