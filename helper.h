#ifndef HELPER_H
#define HELPER_H

int findbyid(string id)
{
    return findattribval(0, "point", "id", id);
}

int[] findarraybyid(string[] ids)
{
    int result[] = {}
    foreach (string id; ids)
        append(result, findbyid(id));
    return result;
}

vector findpositionbyid(string id)
{
    int point_number = findbyid(id);
    if (point_number < 0)
        error("Expected point with id %s", id);
    return point(0, "P", point_number);
}

string[] prefixarray(string array[]; string prefix)
{
    string prefixed[] = {};
    foreach (string value; array)
        append(prefixed, prefix + value);
    return prefixed;
}

void setid(int points[]; string ids[])
{
    if (len(points) != len(ids))
        error("Expected matching point and id array sizes");

    for (int index = 0; index < len(points); ++index)
        setpointattrib(0, "id", points[index], ids[index], "set");
}

int fillfacebyids(string ids[])
{
    int prim = addprim(0, "poly");
    foreach (string id; ids) {
        int point_number = findbyid(id);
        if (point_number < 0)
            error("Expected point with id %s", id);
        addvertex(0, prim, point_number);
    }
    return prim;
}

int fillfacebypoints(int points[])
{
    int prim = addprim(0, "poly");
    foreach (int point_number; points)
        addvertex(0, prim, point_number);
    return prim;
}

void findquadpolyextrudesplits(int split_points[]; string split_group)
{
    foreach (int point_number; split_points) {
        int primitives[] = pointprims(0, point_number);
        if (len(primitives) != 2)
            error("Expected point %d to belong to exactly 2 primitives, got %d", point_number, len(primitives));

        int first_points[] = primpoints(0, primitives[0]);
        int second_points[] = primpoints(0, primitives[1]);

        int common_points[];
        foreach (int p; first_points) {
            if (find(second_points, p) >= 0)
                append(common_points, p);
        }

        if (len(common_points) != 2)
            error("Expected primitives %d and %d around point %d to share exactly 2 points, got %d", primitives[0], primitives[1], point_number, len(common_points));

        if (find(common_points, point_number) < 0)
            error("Shared edge between primitives %d and %d does not contain point %d", primitives[0], primitives[1], point_number);

        foreach (int primitive; primitives) {
            int points[] = primpoints(0, primitive);
            if (len(points) != 4)
                error("Expected primitive %d to be a quad, got %d points", primitive, len(points));

            int opposite_points[];
            foreach (int p; points) {
                if (find(common_points, p) < 0)
                    append(opposite_points, p);
            }

            if (len(opposite_points) != 2)
                error("Could not determine opposite edge of primitive %d", primitive);

            setedgegroup(0, split_group, opposite_points[0], opposite_points[1], 1);
        }
    }
}

#endif
