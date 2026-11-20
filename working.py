import copy

def main(**kwargs):
    publish_assembly = kwargs.pop("publish_assembly", True)
    assembly_only = kwargs.pop("assembly_only", False)
    if assembly_only:
        import turret_assembly
        turret_assembly.main(**kwargs)
        return
    kwargs.setdefault("review_first", True)
    run_oomp_populate = kwargs.get("run_oomp_populate", True)
    #run_oomp_populate = False
    kwargs["run_oomp_populate"] = run_oomp_populate

    run_oomp = kwargs.get("run_oomp", True)
    #run_oomp = False
    kwargs["run_oomp"] = run_oomp

    run_svg = kwargs.get("run_svg", True)
    kwargs["run_svg"] = run_svg

    run_scad = kwargs.get("run_scad", True)
    #run_scad = False
    kwargs["run_scad"] = run_scad

    run_action = kwargs.get("run_action", False)
    #run_action = False
    kwargs["run_action"] = run_action

    generate_stl = kwargs.get("generate_stl", True)
    #generate_stl = True
    kwargs["generate_stl"] = generate_stl

    run(**kwargs)
    if publish_assembly and run_scad and generate_stl:
        import turret_assembly
        turret_assembly.main(**kwargs)

def run(**kwargs):

    import working_cad
    selected_solidcraft = working_cad.solidcraft_mode(kwargs.get("run_solidcraft", False))
    native_context = dict(kwargs.pop("solidcraft_context", None) or {})
    if selected_solidcraft == "working_scad":
        native_context["recipe_source"] = "working_scad"
    native_context["export_extras"] = kwargs.pop("export_extras", native_context.get("export_extras", False))
    native_context["export_stl"] = kwargs.pop("export_stl", native_context.get("export_stl", False))
    native_context["verify_solidcraft"] = kwargs.pop("verify_solidcraft", native_context.get("verify_solidcraft", False))


    kwargs_2 = copy.deepcopy(kwargs)
    #pop run and generate variables from kwargs
    pop_values = ["run_oomp_populate", "run_oomp", "run_scad", "run_action", "generate_stl", "run_svg", "run_solidcraft", "solidcraft_context", "review_first"]
    for key in pop_values:
        kwargs_2.pop(key, None)


    if kwargs.get("run_oomp_populate", False):
        import working_oomp_populate
        working_oomp_populate.main(**kwargs_2)

    if kwargs.get("run_oomp", False):
        import working_oomp
        oomp_kwargs = copy.deepcopy(kwargs_2)
        if kwargs.get("run_solidcraft", False):
            oomp_kwargs["wait_for_completion"] = True
        working_oomp.main(**oomp_kwargs)

    if kwargs.get("run_svg", False) and kwargs.get("review_first", False):
        import working_svg
        working_svg.main(**kwargs_2)

    if kwargs.get("run_scad", False):        
        kwargs2 = copy.deepcopy(kwargs_2)
        if kwargs.get("generate_stl", False):
            kwargs2["typ"] = "all"
        import working_scad
        working_scad.main(**kwargs2)

    #add run_svg
    if kwargs.get("run_svg", False) and not kwargs.get("review_first", False):
        import working_svg
        working_svg.main(**kwargs_2)


    if kwargs.get("run_action", False):
        import working_action
        working_action.main(**kwargs)    

    # Opt-in native route runs after legacy actions/OOMP regeneration.
    if kwargs.get("run_solidcraft", False):
        import working_solidcraft
        working_solidcraft.main(solidcraft_context=native_context)




if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly-only", action="store_true")
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--filter", default="")
    options = parser.parse_args()
    main(assembly_only=options.assembly_only, publish_assembly=not options.geometry_only, filter=options.filter)
