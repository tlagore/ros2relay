class MessageMetrics:
    def __init__(self):
        """ """
        self.byte_sum = 0
        self.message_count = 0

    def increment_message_count(self, message_size):
        self.message_count += 1
        self.byte_sum += message_size

    def get_and_reset_metrics(self):
        m_count = self.message_count
        b_sum = self.byte_sum

        self.message_count = 0
        self.byte_sum = 0

        return (m_count, b_sum)


class MessageMetricsHandler:
    metric_handlers = []
    
    def __init__(self, num_handlers):
        """ """
        for i in range(num_handlers):
            self.metric_handlers.append(MessageMetrics())

    def handle_message(self, handler, message_size):
        if handler > len(self.metric_handlers) - 1 or handler < 0:
            raise ValueError(f"Handler must be between 0 and {len(self.metric_handlers) - 1}")

        self.metric_handlers[handler].increment_message_count(message_size)

    def publish_metrics(self):
        """ """
        # list of tuples (message_count, byte_sum) for each worker
        vals = [m.get_and_reset_metrics() for m in self.metric_handlers]

        # summed tuple, [sum(message_count), sum(byte_sum)]
        sums = [sum(x) for x in zip(*vals)]

        message = f"Messages processed/second: {sums[0]}. KBytes processed/second: {(sums[1] / 1024):.2f}"
        print(message.ljust(len(message)+20), end='')
        print("\r", end='')