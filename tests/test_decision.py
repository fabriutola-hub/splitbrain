"""The two-author decision protocol, with no model involved."""

from __future__ import annotations

import pytest

from splitbrain.core.decision import DecisionMachine, DecisionState

ACCEPTED: tuple[str, ...] = (
    "confirm",
    "confirmed",
    "Confirmed, I'll email them now.",
    "CONFIRMED.",
    "agree",
    "agreed",
    "Agreed!",
    "yes",
    "Yes, sounds right",
    "yep",
    "ok",
    "okay",
    "Okay.",
    "sounds good",
    "Sounds good!",
    "approved",
    "Approved",
    "lgtm",
    "LGTM.",
    "👍",
    "✅",
    "sí",
    "SÍ.",
    "de acuerdo",
    "De acuerdo.",
    "confirmo",
    "Confirmo!",
    "aprobado",
    "Aprobado.",
)

REJECTED: tuple[str, ...] = (
    "no",
    "No",
    "nope",
    "maybe",
    "I don't agree",
    "not confirmed",
    "confirmation pending",
    "confirmable",
    "since we agreed",
    "agreement",
    "wrong",
    "",
    "I confirm",
    "si quieres, esperamos",  # "si" = "if" in Spanish, never a confirmation
)


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


def test_proposal_is_announced_in_the_room_with_its_literal_text() -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("tomas", "decision: SSO in Q1")
    assert outcome.announce is True
    assert outcome.reply == (
        'Proposal v1 from @tomas: "SSO in Q1". '
        "@maria, reply confirm to close it, or write your own decision: ..."
    )


def test_replaced_proposal_is_announced_again() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO on December 1")
    outcome = machine.handle("maria", "decision: SSO on December 15 instead")
    assert outcome.state == DecisionState.PROPOSED
    assert outcome.decision == "SSO on December 15 instead"
    assert outcome.announce is True
    assert 'Proposal v2 from @maria: "SSO on December 15 instead"' in (outcome.reply or "")


def test_non_owner_is_ignored_and_warned_once() -> None:
    machine = DecisionMachine("maria", "tomas")
    first = machine.handle("lucia", "decision: I decide this")
    assert first.state == DecisionState.OPEN
    assert first.reply == "Only @maria and @tomas can close this conflict."
    assert first.announce is False
    assert machine.handle("lucia", "decision: I insist").reply is None
    assert machine.state == DecisionState.OPEN


def test_same_person_cannot_self_confirm() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO beta on Dec 15")
    outcome = machine.handle("maria", "Confirmed, I'll email them now.")
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


def test_only_literal_confirm_without_a_proposal_gets_a_reply() -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("tomas", "confirm")
    assert outcome.state == DecisionState.OPEN
    assert outcome.reply == "There is no pending decision to confirm."


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "ok",
        "okay",
        "sí",
        "👍",
        "✅",
        "agreed",
        "Confirmed, I'll email them now.",
        "ok but not December",
        "si quieres, esperamos",
    ],
)
def test_natural_words_without_a_proposal_are_ignored_silently(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("tomas", text)
    assert outcome.state == DecisionState.OPEN
    assert outcome.reply is None


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


@pytest.mark.parametrize("text", ACCEPTED)
def test_every_natural_confirmation_is_accepted(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: agreed text")
    outcome = machine.handle("tomas", text)
    assert outcome.state == DecisionState.DECIDED
    assert outcome.confirmed_by == "tomas"
    assert outcome.decision == "agreed text"


@pytest.mark.parametrize("text", REJECTED)
def test_every_other_answer_is_ignored(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: agreed text")
    outcome = machine.handle("tomas", text)
    assert outcome.state == DecisionState.PROPOSED
    assert outcome.reply is None
    assert outcome.confirmed_by is None


@pytest.mark.parametrize("text", ["confirmed", "CONFIRMED, I'll email them now.", "Sí.", "✅"])
def test_confirmations_ignore_case_and_trailing_punctuation(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO in Q1")
    assert machine.handle("tomas", text).state == DecisionState.DECIDED


def test_spanish_si_without_an_accent_is_not_a_confirmation() -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO in Q1")
    # "si" means "if" in Spanish: "if you want, we wait".
    outcome = machine.handle("tomas", "si quieres, esperamos")
    assert outcome.state == DecisionState.PROPOSED
    assert outcome.reply is None
    assert machine.handle("tomas", "SÍ.").state == DecisionState.DECIDED


@pytest.mark.parametrize(
    "text",
    [
        "ok but not December",
        "yes, pero en enero",
        "agreed, but let me check with legal",
        "sí, no todavía",
        "confirm, not yet",
        "approved, pero solo en enero",
    ],
)
def test_contrast_after_a_confirmation_word_does_not_close_the_decision(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    machine.handle("maria", "decision: SSO in Q1")
    outcome = machine.handle("tomas", text)
    assert outcome.state == DecisionState.PROPOSED
    assert "v1 is still open" in (outcome.reply or "")
    assert machine.handle("tomas", "confirm").state == DecisionState.DECIDED


@pytest.mark.parametrize("ending", [".", "!", "?", ". "])
def test_quoted_sentence_never_doubles_terminal_punctuation(ending: str) -> None:
    from splitbrain.core.decision import quoted_sentence

    text = f"SSO beta for Acme on December 15{ending.rstrip()}"
    result = quoted_sentence(text)
    assert result.startswith('"') and result.endswith('"')
    assert '"."' not in result and '"!"' not in result and '"?"' not in result


def test_quoted_sentence_adds_one_full_stop_when_missing() -> None:
    from splitbrain.core.decision import quoted_sentence

    assert quoted_sentence("SSO in Q1") == '"SSO in Q1".'


@pytest.mark.parametrize(
    "text",
    [
        "SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
        "SSO ships in Q1!",
        "Are we shipping in Q1?",
    ],
)
def test_proposal_announcement_has_no_doubled_full_stop(text: str) -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("maria", f"decision: {text}")
    assert outcome.reply is not None
    assert f'"{text}"' in outcome.reply
    assert '".' not in outcome.reply and '"!' not in outcome.reply and '"?' not in outcome.reply


def test_proposal_without_terminal_punctuation_gets_exactly_one_stop() -> None:
    machine = DecisionMachine("maria", "tomas")
    outcome = machine.handle("maria", "decision: SSO in Q1")
    assert outcome.reply is not None
    assert 'Proposal v1 from @maria: "SSO in Q1". @tomas' in outcome.reply
