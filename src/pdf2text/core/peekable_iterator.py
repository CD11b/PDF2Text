from itertools import tee

class PeekableIterator:

    def __init__(self, iterable):
        self.iterator, self.peek_iterator = tee(iterable)
        self._advance_peek()

    def _advance_peek(self):
        try:
            self._peeked = next(self.peek_iterator)
            self._has_peek = True
        except StopIteration:
            self._has_peek = False

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self.iterator)
        self._advance_peek()
        return item

    def peek(self):
        return self._peeked if self._has_peek else None

    def has_next(self):
        return self._has_peek
