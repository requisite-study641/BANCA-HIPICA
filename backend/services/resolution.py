"""
Motor de resolución de duelos hípicos.
"""

def resolve_morocha_duel(duel, official_positions: dict) -> str:
    """
    Resuelve MOROCHA (2vs2).
    official_positions es un diccionario {numero_caballo: puesto_oficial}.
    Gana el lado que tenga al caballo con la MEJOR posición oficial.
    """
    c1 = official_positions.get(duel.horse_creator, 99)
    c2 = official_positions.get(duel.horse_creator_2, 99) if duel.horse_creator_2 else 99
    best_creator = min(c1, c2)

    o1 = official_positions.get(duel.horse_opponent, 99)
    o2 = official_positions.get(duel.horse_opponent_2, 99) if duel.horse_opponent_2 else 99
    best_opponent = min(o1, o2)

    if best_creator < best_opponent:
        return "CREATOR"
    elif best_opponent < best_creator:
        return "OPPONENT"
    else:
        return "TIE"


def resolve_duel_logic(duel, duel_type, official_positions: dict) -> str:
    """
    Evalúa la lógica del duelo y retorna 'CREATOR', 'OPPONENT' o 'TIE'.
    """
    if getattr(duel_type, "is_morocha", False):
        return resolve_morocha_duel(duel, official_positions)

    pos_creator = official_positions.get(duel.horse_creator, 99)
    pos_opponent = official_positions.get(duel.horse_opponent, 99)

    if pos_creator < pos_opponent:
        return "CREATOR"
    elif pos_opponent < pos_creator:
        return "OPPONENT"
    else:
        return "TIE"