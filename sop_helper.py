import hou

import hom_helper


def propagate_parameters(
    parent: hou.SopNode,
    child: hou.SopNode,
    *,
    prefix: str = "",
    skip_params: tuple[str, ...] = (),
) -> None:
    parameters = tuple(
        parameter for parameter in child.parmTuples()
        if parameter[0].isSpare() and parameter.name() not in skip_params
    )
    templates = parent.parmTemplateGroup()
    label_prefix = prefix.rstrip("_").replace("_", " ").title()

    for source in parameters:
        template = source.parmTemplate().clone()
        template.setName(f"{prefix}{template.name()}")
        if label_prefix:
            template.setLabel(f"{label_prefix} {template.label()}")
        templates.append(template)

    parent.setParmTemplateGroup(templates)

    for source in parameters:
        target = parent.parmTuple(f"{prefix}{source.name()}")
        target.set(source.eval())
        for source_parm, target_parm in zip(source, target):
            source_parm.set(target_parm)


def add_merge(
    parent: hou.SopNode,
    name: str,
    *inputs: hou.SopNode,
) -> hou.SopNode:
    merge = parent.createNode("merge", name)
    for index, node in enumerate(inputs):
        merge.setInput(index, node)
    return merge


def add_fuse(
    parent: hou.SopNode,
    name: str,
    p_input: hou.SopNode,
) -> hou.SopNode:
    fuse = parent.createNode("fuse", name)
    fuse.setInput(0, p_input)
    return fuse


def add_mirror(
    parent: hou.SopNode,
    name: str,
    p_input: hou.SopNode,
    axis: hou.Vector3 | tuple[float, float, float],
    keep_original: bool,
    consolidate_unshared: bool,
    *args,
) -> hou.SopNode:
    mirror = parent.createNode("mirror", name, *args)
    mirror.setInput(0, p_input)
    mirror.parm("keepOriginal").set(keep_original)
    mirror.parm("dirx").set(axis[0])
    mirror.parm("diry").set(axis[1])
    mirror.parm("dirz").set(axis[2])
    mirror.parm("consolidateunshared").set(consolidate_unshared)
    return mirror


def add_output(
    parent: hou.SopNode,
    name: str,
    p_input: hou.SopNode,
) -> hou.SopNode:
    output = parent.createNode("null", name)
    output.setInput(0, p_input)
    output.setDisplayFlag(True)
    output.setRenderFlag(True)
    return output


def add_outside_recalculation(
    parent: hou.SopNode,
    name: str,
    p_input: hou.SopNode,
    reverse: bool = False,
) -> hou.SopNode:
    subnet = parent.createNode("subnet", name)
    subnet.setInput(0, p_input)

    indirect_input = subnet.indirectInputs()[0]
    clean_orient = subnet.createNode("clean", "orient_polygons")
    clean_orient.setInput(0, indirect_input)
    clean_orient.parm("orientpoly").set(1)
    clean_orient.parm("reversewinding").set(0)
    clean_orient.parm("deldegengeo").set(0)
    clean_orient.parm("delunusedpts").set(0)
    clean_orient.parm("removeunusedgrp").set(0)
    clean_orient.parm("deleteoverlap").set(0)
    clean_orient.parm("delnans").set(0)
    clean_orient.parm("delete_small").set(0)
    clean_orient.parm("fixoverlap").set(0)
    clean_orient.parm("fusepts").set(0)

    calc = hom_helper.sopify(subnet, clean_orient, _check_majority_insides)

    clean_reverse = subnet.createNode("clean", "reverse_winding")
    clean_reverse.setInput(0, calc)
    clean_reverse.parm("orientpoly").set(0)
    expression = '1 - detail(0, "tmp_reverse_winding", 0)' if reverse else 'detail(0, "tmp_reverse_winding", 0)'
    clean_reverse.parm("reversewinding").setExpression(expression)
    clean_reverse.parm("deldegengeo").set(0)
    clean_reverse.parm("delunusedpts").set(0)
    clean_reverse.parm("removeunusedgrp").set(0)
    clean_reverse.parm("deleteoverlap").set(0)
    clean_reverse.parm("delnans").set(0)
    clean_reverse.parm("delete_small").set(0)
    clean_reverse.parm("fixoverlap").set(0)
    clean_reverse.parm("fusepts").set(0)

    cleanup = hom_helper.sopify(subnet, clean_reverse, _cleanup_recalculate_outside)
    add_output(subnet, "OUT", cleanup)
    subnet.layoutChildren()
    return subnet

def _check_majority_insides(node: hou.SopNode) -> None:
    geo = node.geometry()
    prims = geo.prims()
    is_closed = bool(prims) and all(p.intrinsicValue("closed") for p in prims) and not any(len(e.prims()) < 2 for e in geo.globEdges("*"))
    is_inside = False
    if is_closed:
        vol = sum(p.intrinsicValue("measuredvolume") for p in prims)
        is_inside = vol < 0
    hom_helper.add_new_attr(geo, hou.attribType.Global, "tmp_reverse_winding", 0)
    geo.setGlobalAttribValue("tmp_reverse_winding", 1 if is_inside else 0)

def _cleanup_recalculate_outside(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.remove_attributes(geo, global_attribs="tmp_reverse_winding")
