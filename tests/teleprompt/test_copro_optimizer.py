import textwrap

import dspy
from dspy import Example
from dspy.teleprompt.signature_opt import COPRO
from dspy.utils.dummies import DummyLM


# Define a simple metric function for testing
def simple_metric(example, prediction):
    # Simplified metric for testing: true if prediction matches expected output
    return example.output == prediction.output


# Example training and validation sets
trainset = [
    Example(input="Question: What is the color of the sky?", output="blue").with_inputs("input"),
    Example(input="Question: What does the fox say?", output="Ring-ding-ding-ding-dingeringeding!").with_inputs(
        "input"
    ),
]


def test_signature_optimizer_initialization():
    optimizer = COPRO(metric=simple_metric, breadth=2, depth=1, init_temperature=1.4)
    assert optimizer.metric == simple_metric, "Metric not correctly initialized"
    assert optimizer.breadth == 2, "Breadth not correctly initialized"
    assert optimizer.depth == 1, "Depth not correctly initialized"
    assert optimizer.init_temperature == 1.4, "Initial temperature not correctly initialized"


class SimpleModule(dspy.Module):
    def __init__(self, signature):
        super().__init__()
        # COPRO doesn't work with dspy.Predict
        self.predictor = dspy.ChainOfThought(signature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)


def test_signature_optimizer_optimization_process():
    optimizer = COPRO(metric=simple_metric, breadth=2, depth=1, init_temperature=1.4)
    dspy.settings.configure(
        lm=DummyLM(
            [
                "[[ ## proposed_instruction ## ]]\nOptimized instruction 1\n\n"
                "[[ ## proposed_prefix_for_output_field ## ]]\nOptimized instruction 2",
            ]
        )
    )

    student = SimpleModule("input -> output")

    # Assuming the compile method of COPRO requires a student module, a development set, and evaluation kwargs
    optimized_student = optimizer.compile(
        student, trainset=trainset, eval_kwargs={"num_threads": 1, "display_progress": False}
    )

    # Check that the optimized student has been modified from the original
    # This check can be more specific based on how the optimization modifies the student
    assert optimized_student is not student, "Optimization did not modify the student"

    # Further tests can be added to verify the specifics of the optimization process,
    # such as checking the instructions of the optimized student's predictors.


def test_signature_optimizer_statistics_tracking():
    optimizer = COPRO(metric=simple_metric, breadth=2, depth=1, init_temperature=1.4)
    optimizer.track_stats = True  # Enable statistics tracking

    dspy.settings.configure(
        lm=DummyLM(
            [
                "[[ ## proposed_instruction ## ]]\nOptimized instruction 1\n\n"
                "[[ ## proposed_prefix_for_output_field ## ]]\nOptimized instruction 2",
            ]
        )
    )
    student = SimpleModule("input -> output")
    optimized_student = optimizer.compile(
        student, trainset=trainset, eval_kwargs={"num_threads": 1, "display_progress": False}
    )

    # Verify that statistics have been tracked and attached to the optimized student
    assert hasattr(optimized_student, "total_calls"), "Total calls statistic not tracked"
    assert hasattr(optimized_student, "results_best"), "Best results statistics not tracked"


# Assuming the setup_signature_optimizer fixture and simple_metric function are defined as before


def test_optimization_and_output_verification():
    lm = DummyLM(
        [
            "[[ ## proposed_instruction ## ]]\nOptimized Prompt\n\n[[ ## proposed_prefix_for_output_field ## ]]\nOptimized Prefix",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
            "[[ ## reasoning ## ]]\nfrance\n\n[[ ## output ## ]]\nParis",
        ]
    )
    dspy.settings.configure(lm=lm)
    optimizer = COPRO(metric=simple_metric, breadth=2, depth=1, init_temperature=1.4)

    student = SimpleModule("input -> output")

    # Compile the student with the optimizer
    optimized_student = optimizer.compile(
        student, trainset=trainset, eval_kwargs={"num_threads": 1, "display_progress": False}
    )

    # Simulate calling the optimized student with a new input
    test_input = "What is the capital of France?"
    prediction = optimized_student(input=test_input)

    print(lm.get_convo(-1))

    assert prediction.output == "Paris"

    for message in lm.get_convo(-1)[0]:
        print("----")
        print(textwrap.indent(message["content"], "                "))
        print("----")
    assert lm.get_convo(-1)[0] == [
        {
            "role": "system",
            "content": textwrap.dedent(
                """\
                Your input fields are:
                1. `input` (str)

                Your output fields are:
                1. `reasoning` (str)
                2. `output` (str)

                All interactions will be structured in the following way, with the appropriate values filled in.

                [[ ## input ## ]]
                {input}

                [[ ## reasoning ## ]]
                {reasoning}

                [[ ## output ## ]]
                {output}

                [[ ## completed ## ]]

                In adhering to this structure, your objective is: 
                        Optimized Prompt"""
            ),
        },
        {
            "role": "user",
            "content": textwrap.dedent(
                """\
                [[ ## input ## ]]
                What is the capital of France?

                Respond with the corresponding output fields, starting with the field `reasoning`, then `output`, and then ending with the marker for `completed`."""
            ),
        },
    ]


def test_statistics_tracking_during_optimization():
    dspy.settings.configure(
        lm=DummyLM(
            [
                "[[ ## proposed_instruction ## ]]\nOptimized Prompt\n\n"
                "[[ ## proposed_prefix_for_output_field ## ]]\nOptimized Prefix",
            ]
        )
    )

    optimizer = COPRO(metric=simple_metric, breadth=2, depth=1, init_temperature=1.4)
    optimizer.track_stats = True  # Enable statistics tracking

    student = SimpleModule("input -> output")
    optimized_student = optimizer.compile(
        student, trainset=trainset, eval_kwargs={"num_threads": 1, "display_progress": False}
    )

    # Verify that statistics have been tracked
    assert hasattr(optimized_student, "total_calls"), "Optimizer did not track total metric calls"
    assert optimized_student.total_calls > 0, "Optimizer reported no metric calls"

    # Check if the results_best and results_latest contain valid statistics
    assert "results_best" in optimized_student.__dict__, "Optimizer did not track the best results"
    assert "results_latest" in optimized_student.__dict__, "Optimizer did not track the latest results"
    assert len(optimized_student.results_best) > 0, "Optimizer did not properly populate the best results statistics"
    assert (
        len(optimized_student.results_latest) > 0
    ), "Optimizer did not properly populate the latest results statistics"

    # Additional detailed checks can be added here to verify the contents of the tracked statistics
