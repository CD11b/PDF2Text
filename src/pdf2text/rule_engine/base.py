from src.pdf2text.models.decisions.decision import Decision

class Rule:
    priority = None
    enabled = None

    def __init__(self, priority=None, enabled=None):
        self.priority = (priority if priority is not None else (self.__class__.priority if self.__class__.priority is not None else 999))
        self.enabled = (enabled if enabled is not None else (self.__class__.enabled if self.__class__.enabled is not None else True))

    @property
    def name(self):
        return self.__class__.__name__

    def matches(self, ctx) -> bool:
        raise NotImplementedError

    def decide(self, ctx) -> Decision:
        raise NotImplementedError

class RuleEngine:

    def __init__(self, rules):
        self.rules = sorted((r for r in rules if r.enabled), key=lambda r: r.priority)

    def decide(self, ctx):
        for rule in self.rules:
            if rule.matches(ctx):
                return rule.decide(ctx)
        raise RuntimeError(f"No rule matched context: {ctx}. Missing a fallback rule.")