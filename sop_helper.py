import hou


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
