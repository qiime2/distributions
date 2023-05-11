import os
import sys
import json


def ActionAdapter(function, **extras):
    """Evaluate a main function in a github action

    * Assumes that sys.stdin contains JSON arguments for `function` (main).
    * The keys will have dashes converted to underscores.
    * `function` may return a dictionary of results in which case they will
      be set as the output for the step using $GITHUB_OUTPUT
    * The keys of the outputs will have underscores converted to dashes

    Typical usage would look like:

    - run: echo ${{ toJSON(inputs) }} | ./script.py

    """
    print(' == Starting == ', flush=True)

    arguments = json.load(sys.stdin)
    kwargs = {k.replace('-', '_'): v for k, v in arguments.items()}
    for key, val in kwargs.items():
        if type(val) is str and (val.startswith('[') or val.startswith('{')):
            try:
                kwargs[key] = json.loads(val)
            except Exception:
                pass


    print(' == Using inputs == ')
    print(json.dumps(arguments, indent=2), flush=True)
    if extras:
        print(json.dumps(extras, indent=2), flush=True)
    print(' == Evaluated keyword arguments == ')
    print(json.dumps(kwargs, indent=2), flush=True)

    print(' == Executing == ', flush=True)
    results = function(**kwargs, **extras)

    if results:
        print(' == Outputs == ')
        results = {k.replace('_', '-'): v for k, v in results.items()}
        print(json.dumps(results, indent=2), flush=True)

        lines = []
        for param, arg in results.items():
            if type(arg) is dict or type(arg) is list:
                arg = json.dumps(arg)
            lines.append(f'{param}={arg}\n')

        output_path = os.environ.get('GITHUB_OUTPUT')
        if output_path is None:
            raise Exception('Missing $GITHUB_OUTPUT, not in a github runner.')

        with open(output_path, mode='a') as fh:
            fh.write(''.join(lines))
    else:
        print(' == No outputs == ')

    print(' == Done == ', flush=True)
