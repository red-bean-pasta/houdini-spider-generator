from ...helper import affix_id

def tmp_coxa_start(*i) -> str:
    return affix_id("tmp_pedipalpcoxastart", *i)
def tmp_coxa_end(*i) -> str:
    return affix_id("tmp_pedipalpcoxaend", *i)
def tmp_coxa_support(*i) -> str:
    return affix_id("tmp_pedipalpcoxasupport", *i)
def tmp_coxa_corner(*i) -> str:
    return affix_id("tmp_pedipalpcoxacorner", *i)
def tmp_maxilla_pole(*i) -> str:
    return affix_id("tmp_maxillapole", *i)

def tmp_front_socket_size() -> str:
    return "tmp_frontsocketwidth"
def tmp_chelicerae_start_z() -> str:
    return "tmp_cheliceraestartz"