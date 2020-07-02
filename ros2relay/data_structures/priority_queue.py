from queue import Queue
import time

class PriorityQueue(Generic(T)):
    """ implements a priority queue """

    # an array of deque, one for each priority level
    queues = []
    priority_levels = 1
    
    def __init__(self, priority_levels=1):
        """
        constructor for PriorityQueue. Defaults to 1 priority level, or just a regular queue
        """

        if priority_levels < 1:
            raise ValueError("number of priority levels must be greater than 0")

        self.priority_levels = priority_levels
        
        for i in range(priorityLevels - 1):
            queues.append(Queue())

        q = Queue()
        
        
    
    def enqueue(self, item, priority):
        if priority > priority_levels or priority < 1:
            raise ValueError(f"priority must be between 1 and {self.priority_levels}")

        queues[priority - 1].put_nowait(item)

    def dequeue(self, block=True):
        """ 
        blocking function gets a top priority item from the queue.

        Note: if there is no data in priority queue, this method does not guarantee that the next item retrieved from the queue will be the highest priority that was added since the call to dequeue 
        """
        #try to get a top priority item
        data = self.queues[0].get_nowait()

        #if we didn't get a top priority item, spin our 
        while not data:
            for i in range(self.priority_levels - 1):
                data = self.queues[i].get_nowait()
                if(data):
                    return data

            if not block:
                return None
                
            time.sleep(0.05)

        return data

    def dequeue(self, priority):
        """
        blocking function
        """
        if priority > priority_levels or priority < 1:
            raise ValueError(f"priority must be between 1 and {self.priority_levels}")
    

