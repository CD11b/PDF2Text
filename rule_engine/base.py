from models import Decision

class Rule:
    priority = 999
    name = None

    def __init__(self):
        if self.name is None:
            self.name = self.__class__.__name__

    def matches(self, ctx, layout, groups_iter) -> bool:
        raise NotImplementedError

    def decide(self, ctx) -> Decision:
        raise NotImplementedError

class RuleEngine:

    def __init__(self, rules):
        self.rules = sorted(rules, key=lambda r: r.priority)

    def decide(self, ctx, layout, groups_iter):
        for rule in self.rules:
            if rule.matches(ctx, layout, groups_iter):
                return rule.decide(ctx)
        return None