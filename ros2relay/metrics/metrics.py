import threading


class MessageMetrics:
    def __init__(self):
        """ """
        self.byte_sum = 0
        self.message_count = 0
        self.message_handle_time = 0

    def increment_message_count(self, message_size, time_taken):
        self.message_count += 1
        self.byte_sum += message_size
        self.message_handle_time += time_taken

    def get_and_reset_metrics(self):
        m_count = self.message_count
        b_sum = self.byte_sum
        t_taken = self.message_handle_time

        self.message_count = 0
        self.byte_sum = 0
        self.message_handle_time = 0

        return (m_count, b_sum, t_taken)


class MessageMetricsHandler:
    def __init__(self, num_handlers, count_drops=False):
        """ """
        self.dropped_messages = 0
        self.dropped_per_period = 0
        self.dropped_lock = threading.Lock()

        self.observed_messages = 0
        self.observed_lock = threading.Lock()

        self.metric_handlers = []
        self.count_drops = count_drops

        for i in range(num_handlers):
            self.metric_handlers.append(MessageMetrics())

    def handle_message(self, handler, message_size, time_taken):
        if handler > len(self.metric_handlers) - 1 or handler < 0:
            raise ValueError(f"Handler must be between 0 and {len(self.metric_handlers) - 1}")

        self.metric_handlers[handler].increment_message_count(message_size, time_taken)

    def publish_metrics(self):
        """ """
        # list of tuples (message_count, byte_sum, time_taken) for each worker
        vals = [m.get_and_reset_metrics() for m in self.metric_handlers]

        # summed tuple, [sum(message_count), sum(byte_sum), sum(time_taken)]
        sums = [sum(x) for x in zip(*vals)]

        handle_time = 0 if sums[0] == 0 else sums[2]/sums[0]

        if self.count_drops:
            message = f"m/s observed: {self.observed_messages}. m/s:{sums[0]}. d:{self.dropped_messages} d/s:{self.dropped_per_period} KB/s:{(sums[1] / 1024):.2f}. t/s:{handle_time:.2f}"
            print(message.ljust(len(message)+20), end='')
            print("\r", end='')

            with self.dropped_lock:
                self.dropped_per_period = 0
        else:
            message = f"m/s observed: {self.observed_messages}. m/s sent:{sums[0]}. KB/s:{(sums[1] / 1024):.2f}. t/m/s:{handle_time:.2f}"
            print(message.ljust(len(message)+20), end='')
            print("\r", end='')

        # only lock once per publish period to ensure we reset observed
        with self.observed_lock:
            self.observed_messages = 0
    
    def increment_dropped(self):
        # shouldn't be calling this if we haven't enabled drop counters
        if self.count_drops:
            with self.dropped_lock:
                self.dropped_messages += 1
                self.dropped_per_period += 1

    def increment_observed(self):
        # to not put a lock in hot path, observed messages is not thread safe on increment
        self.observed_messages += 1