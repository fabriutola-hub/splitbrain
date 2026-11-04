"""SPEC 4.6 step 5: the two-author decision protocol, no model involved."""

from __future__ import annotations

import pytest

from splitbrain.core.decision import DecisionMachine, DecisionState


def test_proposal_then_other_author_confirms() -> None:
    machine = DecisionMachine("maria", "tomas")
    assert machine.handle("maria", "decision: SSO beta for Acme on Dec 15, GA in Q1.").state == (
        DecisionState.PROPOSED
    )
    outcome = machine.handle("tomas", "confirm")
    assert outcome.state == DecisionState.DECIDED
    assert outcome.decision == "SSO beta for Acme on Dec 15, GA in Q1."
    assert outcome.proposed_by == "maria"
    assert outcome.confirmed_by == "tomas"
    assert outcome.decided_at


def test_non_owner_is_ignored_and_warned_once() -> None:
    machine = DecisionMachine("maria", "tomas")
    first = machine.handle("lucia", "decision: I decide this")
    assert first.state == DecisionState.OPEN
    assert first.reply == "Only @maria and @tomas can close this conflict."
    assert machine.handle("lucia", "decision: I insist").reply is None
    assert machine.state == DecisionState.OPEN


def test_same_person_cannot_self_confirm() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO beta on Dec 15")
    outcome = machine.handle("maria", "confirm")
    assert outcome.state == DecisionState.PROPOSED
    assert outcome.reply == "Only @tomas can confirm this decision."
    assert machine.handle("tomas", "confirmo").state == DecisionState.DECIDED


def test_new_proposal_replaces_a_pending_one() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO on December 1")
    machine.handle("tomas", "decisión: SSO on December 15 instead")
    assert machine.state == DecisionState.PROPOSED
    assert machine.decision == "SSO on December 15 instead"
    assert machine.proposed_by == "tomas"
    assert machine.handle("maria", "de acuerdo").state == DecisionState.DECIDED


def test_confirm_without_a_proposal_is_refused() -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("tomas", "agree")
    assert outcome.state == DecisionState.OPEN
    assert outcome.reply == "There is no pending decision to confirm."


def test_decided_state_is_terminal() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: done")
    machine.handle("tomas", "confirm")
    after = machine.handle("maria", "decision: actually, one more thing")
    assert after.state == DecisionState.DECIDED
    assert after.decision == "done"


def test_two_different_authors_are_required() -> None:
    with pytest.raises(ValueError, match="two different authors"):
        DecisionMachine("maria", "maria")


@pytest.mark.parametrize("word", ["confirm", "confirmo", "agree", "de acuerdo"])
def test_every_confirmation_word_works(word: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: agreed text")
    assert machine.handle("tomas", word).state == DecisionState.DECIDED
