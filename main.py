#! /usr/bin/env python
import csv
import sys 
from scenario import outage_scenario_generator, failure_scenario_generator, output_scenario, generate_n_unique, stream_scenario_generator, combine_scenarios, scenario_from_csv, n_minus_x_generator
from limits import Limits
from loadflow import Loadflow
from misc import as_csv, grem


def main_outage(num, out_stream):
    batch = generate_n_unique(outage_scenario_generator(open("rts.net")), num)
    output_scenario(batch, out_stream)


def main_n_minus_x(x, no_input, in_stream, out_stream):
    fail_batch = list(n_minus_x_generator(x, open("rts.net")))

    # for information print the unmodified base case
    # and the un-combined failures
    if not no_input:
        out_stream.write("0, base, None, , 1.0\n")

    output_scenario(fail_batch, out_stream)

    # if we didn't have a input file then we are done
    if no_input:
        return

    # otherwise read the input as a list of scenarios and their count
    # for each base combine it with all the failures
    # we ignore the count for the base (not sure what to do with it)
    for base_count, base_scenario in stream_scenario_generator(in_stream):
        out_stream.write(str(base_count) + ", " + str(base_scenario) + "\n")

        for count, fail_scenario in fail_batch:
            new_scenario = combine_scenarios(base_scenario, fail_scenario)
            out_stream.write(str(count) + ", " + str(new_scenario) + "\n")



def main_simulate(in_stream, out_stream):
    limits = Limits(open("rts.lim"))
    loadflow = Loadflow(open("rts.lf"), limits)

    for count, scenario in stream_scenario_generator(in_stream):
        result, result_reason = loadflow.simulate(scenario)
        scenario.result = result
        scenario.result_reason = result_reason
        out_stream.write(str(count) + ", " + str(scenario) + "\n")


def main_failure(num, no_input, in_stream, out_stream):

    fail_batch = generate_n_unique(failure_scenario_generator(open("rts.net")), num)

    # for information print the unmodified base case
    # and the un-combined failures
    if not no_input:
        out_stream.write("0, base, None, , 1.0\n")
    output_scenario(fail_batch, out_stream)

    # if we didn't have a input file then we are done
    if no_input:
        return

    # otherwise read the input as a list of scenarios and their count
    # for each base combine it with all the failures
    # we ignore the count for the base (not sure what to do with it)
    for base_count, base_scenario in stream_scenario_generator(in_stream):
        out_stream.write(str(base_count) + ", " + str(base_scenario) + "\n")

        for count, fail_scenario in fail_batch:
            new_scenario = combine_scenarios(base_scenario, fail_scenario)
            out_stream.write(str(count) + ", " + str(new_scenario) + "\n")


def main_analyse(in_stream, out_stream):
    group = []
    pfail = []

    def output_group_stats(grp):
        group_size = sum(c for c,s in grp)
        failures = float(sum(c for c,s in grp if s.result is False))
        pfail.append(failures/group_size)
        out_stream.write(as_csv([failures, group_size, failures/group_size], ", ") + "\n")

    for count, scenario in stream_scenario_generator(in_stream):
        if scenario.scenario_type == "outage" or scenario.scenario_type == "base":
            if len(group) != 0:
                output_group_stats(group)
                group = []

            # output base stats of new group
            out_stream.write(str(count) + ", " + str(scenario) + "\n")
        else:
            group.append((count, scenario))

    if len(group) != 0:
        output_group_stats(group)
        group = []

    out_stream.write("\n")
    out_stream.write("min , " + str(min(pfail)) + "\n")
    out_stream.write("max , " + str(max(pfail)) + "\n")
    out_stream.write("avg , " + str(sum(pfail)/len(pfail)) + "\n")


def main_test(out_stream):
    """print the results and the intermediate file for 
       a number of interesting scenarios. So we can check
       by hand if the intermediate file generator and the
       simulator are doing the correct thing.
    """

    batch_string = ""
    batch_string += "1, base, None, , 1.0\n"           # base - as normal
    batch_string += "1, half, None, , 0.5\n"           # half load power
    batch_string += "1, island, None, , 1.0, B11\n"    # island
    batch_string += "1, slack, None, , 1.0, G12\n"     # removed 1 slack bus
    batch_string += "1, slack-all, None, , 1.0, G12, G13, G14\n"  # removed all slack busses
    batch_string += "1, bus, None, , 1.0, 104\n"       # remove 1 bus without generators
    batch_string += "1, bus-gen, None, , 1.0, 101\n"   # remove 1 bus with generators attached
    batch_string += "1, line, None, , 1.0, A2\n"       # remove 1 line
    batch_string += "1, gen, None, , 1.0, G24\n"       # remove 1 generator

    in_stream = StringIO(batch_string)
    
    limits = Limits(open("rts.lim"))
    loadflow = Loadflow(open("rts.lf"), limits)

    try:
        shutil.rmtree("test")
    except:
        pass
    finally:
        os.makedirs("test")

    for count, scenario in stream_scenario_generator(in_stream):
        intermediate_file = open("test/" + scenario.scenario_type + ".csv", "w")
        loadflow.lfgenerator(intermediate_file, scenario)
        intermediate_file.close()

        result, result_reason = loadflow.simulate(scenario)
        scenario.result = result
        scenario.result_reason = result_reason
        out_stream.write(str(count) + ", " + str(scenario) + "\n")


def main ():
    from optparse import OptionParser

    parser = OptionParser("e.g. python main.py [test, clean, analyse, simulate, outage, failure, n-x]", 
                          version="1-Oct-09 by James Brooks")
    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.error("expected more arguments")

    in_stream = sys.stdin
    out_stream = sys.stdout

    if args[0] == "outage":
        if len(args) != 2:
            parser.error("expected 2 arguments got " + str(len(args)))
        num = int(args[1])
        retval = main_outage(num, out_stream)

    elif args[0] == "n-x":
        no_input = False
        if len(args) == 3:
            if args[2] == "noInput":
                no_input = True
            else:
                parser.error("expected 2 arguments or 'noInput'.")
        elif len(args) != 2:
            parser.error("expected 2 arguments got " + str(len(args)))
        x = int(args[1])
        retval = main_n_minus_x(x, no_input, in_stream, out_stream)

    elif args[0] == "simulate":
        if len(args) != 1:
            parser.error("expected 1 argument got " + str(len(args)))
        retval = main_simulate(in_stream, out_stream)

    elif args[0] == "failure":
        no_input = False
        if len(args) == 3:
            if args[2] == "noInput":
                no_input = True
            else:
                parser.error("expected 2 arguments or 'noInput'.")
        elif len(args) != 2:
            parser.error("expected 2 arguments got " + str(len(args)))
        num = int(args[1])
        retval = main_failure(num, no_input, in_stream, out_stream)

    elif args[0] == "analyse":
        retval = main_analyse(in_stream, out_stream)

    elif args[0] == "test":
        retval = main_test(out_stream)

    elif args[0] == 'clean':
        retval = 0
        grem(".", r".*\.pyc")
        grem(".", r".*\.csv")

    else:
        parser.error("expected [outage, simulate, failure] got " + str(args[0]))
    
    sys.exit(retval)

if __name__ == "__main__":
    main()

