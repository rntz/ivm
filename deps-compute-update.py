# OBSERVATION:
#
# the thing that dependency tracking does that diffs do NOT is incorporate
# information about DEMAND. a purely diff-based compute/update view assumes we
# compute the entire output all the time.
#
# maybe dependency tracking is like a lense, but in reverse.
# a lens has a forward pass that communicates to a backward pass.
#
# dependency tracking has a backward pass ("here is what I am demanding/reading
# from") that communicates to a forward pass (calculating the requested values).
#
# PROBLEM: with dynamic dependencies the passes are interleaved: I need to
# compute things in order to decide what I'm demanding! This is the
# Applicative/Monad difference in BSalaC.
#
# so I think this isn't quite right.
#
# THE FUNDAMENTAL DIFFICULTY: Reconciling these two views:
#
# 1. It's just a function, input -> output
#
# 2. There is a _flow_ of data, either push (write-oriented) or pull
# (read-oriented). We can do unidirectional flow with only one method, but this
# only gets us so far. Really we want push-write/pull-read interacting. In Make,
# we push-write only to leaves and the rest is pull-read. In Diff Dataflow we
# push basically everywhere - but can pull at leaves, I think? The Makelike/Dep
# interface is about something which has push/write _at least_ at leaves and
# pull/read _at least_ at sinks; what's in between is hidden.
#
# Note that Haskell kinda resolves this! Haskell is "functional" but it has
# pull/demand-based computation!
#
# So to call a function I provide it with things it can read() from, but also, I
# give it a demand. Or perhaps: to call a function, I provide it with things it
# can read() from, and in return, it gives me something I can read() from; but
# read() accepts a 'demand' argument to limit what I am reading.

# Can we do dependencies via a compute/update interface?
from collections import namedtuple
import itertools

# interface for Deps/Makelike
class Deps:
    def read(self, key): pass
    def write(self, key, value): pass

# A dep-like delta is either None (meaning no change) or New(new_value).
New = namedtuple('New', ['value'])

# interface for diffs
class Diffs:
    # You give me inputs, I return outputs.
    #                  A                      → B × S
    #                 ———————————————————————   —
    def compute(self, *inputs, **named_inputs): pass
    # Must call update() only after calling compute() at least once.
    # You give me input deltas, I return output deltas.
    #
    # For dep-like Diffs, a delta is either None or New(new_value).
    #            S × ΔA                     → ΔB × S
    #                ——————————————————————-  —–
    def update(self, *deltas, **named_deltas): pass

# Lifting an arbitrary function into a dep-like Diffs. called "Rerunner" because
# its only strategy is to rerun the underlying function if necessary.
class Rerunner(Diffs):
    def __init__(self, function): self.f = function

    def compute(self, *inputs, **named_inputs):
        # list not tuple b/c needs to be mutable for update() to work
        self.inputs = list(inputs)
        self.named_inputs = named_inputs
        return self.f(*inputs, **named_inputs)

    def update(self, *deltas, **named_deltas):
        changed = False
        for i,x in enumerate(deltas):
            if x is not None:
                assert isinstance(x, New)
                # NB. could do an equality test here to short-circuit!
                changed = True
                self.inputs[i] = x.value
        for k,x in named_deltas.items():
            if x is not None:
                assert isinstance(x, New)
                # NB. could do an equality test here to short-circuit!
                changed = True
                self.named_inputs[k] = x.value
        return self.f(*self.inputs, *self.named_inputs) if changed else None

# Converting a Deps into a dep-like Diffs.
#
# WHAT HAVE WE LOST IN TRANSITION:
#
# 1. Ability to have multiple outputs and only read() some of them.
#    Is there a way to restore this???
#    We could pass the requested output's name as an additional input -
#    but then what does update() produce for the diff??
#
# WHAT WE WANT BUT DO NOT HAVE:
#
# 2. The ability to know whether the result changed.
#    We could restore this by caching previous output & diffing.
#    But this is expensive.
#
class DiffsFrom(Diffs):
    # `target` is the node in the dep graph we treat as our output.
    def __init__(self, deps: Deps, target):
        self.deps = deps
        self.target = target

    # The names are the names of the sources in the Dep graph.
    def compute(self, **named_inputs):
        for k,v in named_inputs.items():
            self.deps.write(k, v)
        return self.deps.read(self.target)

    def update(self, **named_deltas):
        for k,v in named_deltas.items():
            if v is None: continue
            assert isinstance(v, New)
            self.deps.write(k, v.value)
        # PROBLEM: how do we know whether things changed? WE DON'T.
        return New(self.deps.read(self.target))

# Converting a dep-like Diffs into a Deps.
#
# The Diffs is assumed to take named inputs and produce a single output. The
# `key` to read() is ignored. We could instead require the Diffs to produce a
# dictionary and look up the key in it.
#
# This doesn't really matter, because either way we are forced to demand all the
# output for every read() - there is no way to propagate this "demand" into a
# Diffs object. This doesn't mean we lose ALL incrementality; think of a build
# system with only one target, it can still only build those things affected by
# a write and remember intermediate state. But still: we are losing something.
#
# WHAT DO WE LOSE IN TRANSITION?
#
# 1. Explicit information about whether something changed since last read().
#
# WHAT DO WE WANT BUT NOT HAVE:
#
# 2. The ability to read() multiple keys and only compute what's necessary for that key.
class DepsFrom(Deps):
    def __init__(self, diffs: Diffs):
        self.diffs = diffs
        self.inputs = {}        # stores named inputs or their deltas
        self.initialized = False

    def write(self, key, value):
        self.inputs[key] = New(value) if self.initialized else value

    def read(self, _key):
        # We have to do an initial compute.
        if not self.initialized:
            result = self.prev_output = self.diffs.compute(**self.inputs)
            self.initialized = True
        else:
            result = self.diffs.update(**self.inputs)
            if result is None:
                result = self.prev_output
            else:
                assert isinstance(result, New)
                result = self.prev_output = result.value
        # Mark all inputs clean/unmodified.
        self.inputs = {k: None for k in self.inputs}
        return result

# TODO: Pipelining Diffs & composing them into a dataflow graph can be done as
# usual, but there are certain optimizations we can do because we know that all
# diffs are None/New. right?

# TODO: tests.
