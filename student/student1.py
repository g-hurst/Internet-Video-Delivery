from typing import List
import numpy as np

# Adapted from code by Zach Peats

# ======================================================================================================================
# Do not touch the client message class!
# ======================================================================================================================


class ClientMessage:
  """
  This class will be filled out and passed to student_entrypoint for your algorithm.
  """
  total_seconds_elapsed: float	  # The number of simulated seconds elapsed in this test
  previous_throughput: float		  # The measured throughput for the previous chunk in kB/s

  buffer_current_fill: float		    # The number of kB currently in the client buffer
  buffer_seconds_per_chunk: float     # Number of seconds that it takes the client to watch a chunk. Every
                    # buffer_seconds_per_chunk, a chunk is consumed from the client buffer.
  buffer_seconds_until_empty: float   # The number of seconds of video left in the client buffer. A chunk must
                    # be finished downloading before this time to avoid a rebuffer event.
  buffer_max_size: float              # The maximum size of the client buffer. If the client buffer is filled beyond
                    # maximum, then download will be throttled until the buffer is no longer full

  # The quality bitrates are formatted as follows:
  #
  #   quality_levels is an integer reflecting the # of quality levels you may choose from.
  #
  #   quality_bitrates is a list of floats specifying the number of kilobytes the upcoming chunk is at each quality
  #   level. Quality level 2 always costs twice as much as quality level 1, quality level 3 is twice as big as 2, and
  #   so on.
  #       quality_bitrates[0] = kB cost for quality level 1
  #       quality_bitrates[1] = kB cost for quality level 2
  #       ...
  #
  #   upcoming_quality_bitrates is a list of quality_bitrates for future chunks. Each entry is a list of
  #   quality_bitrates that will be used for an upcoming chunk. Use this for algorithms that look forward multiple
  #   chunks in the future. Will shrink and eventually become empty as streaming approaches the end of the video.
  #       upcoming_quality_bitrates[0]: Will be used for quality_bitrates in the next student_entrypoint call
  #       upcoming_quality_bitrates[1]: Will be used for quality_bitrates in the student_entrypoint call after that
  #       ...
  #
  quality_levels: int
  quality_bitrates: List[float]
  upcoming_quality_bitrates: List[List[float]]

  # You may use these to tune your algorithm to each user case! Remember, you can and should change these in the
  # config files to simulate different clients!
  #
  #   User Quality of Experience =    (Average chunk quality) * (Quality Coefficient) +
  #                                   -(Number of changes in chunk quality) * (Variation Coefficient)
  #                                   -(Amount of time spent rebuffering) * (Rebuffering Coefficient)
  #
  #   *QoE is then divided by total number of chunks
  #
  quality_coefficient: float
  variation_coefficient: float
  rebuffering_coefficient: float
# ======================================================================================================================


# Your helper functions, variables, classes here. You may also write initialization routines to be called
# when this script is first imported and anything else you wish.
DBG = False
def print_dbg(*args):
    global DBG
    if DBG: print(*args)

class BBA_2():
    def __init__(self):
        self.reservoir = None
        self.qual_prev = 0
        self.R_prev    = 0
        self.alpha     = 0.5 # exponential smoothing factor for reservoir
        self.buffer_capacity_prev = 0
        self.do_quickstart = True

        self.quals = []
        self.counts = [0,0,0]

    def __str__(self):
        msg = f'bb2:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        return msg
    
    def map_buff_to_quality(self, clt_msg: ClientMessage):
        bitrates = clt_msg.quality_bitrates
        R_min = min(bitrates)
        R_max = max(bitrates)
        buff_scaled = self.buffer_capacity / clt_msg.buffer_max_size # scale buffer occupancy to [0,1]
        buff_scaled = buff_scaled * (R_max - R_min) + R_min          # scale buffer buffer occupancy to [min(bitrates), max(bitrates)]
        
        try:    R_minus = max([r for r in bitrates if r < self.R_prev])
        except: R_minus = self.R_prev
        try:    R_plus  = min([r for r in bitrates if r > self.R_prev])
        except: R_plus  = self.R_prev
        # print_dbg(f'{buff_scaled} -> [{R_minus}, {R_plus}]')

        if   buff_scaled <= R_minus:
            try:    R_next = max(filter(lambda x: x > buff_scaled, bitrates))
            except: R_next = self.R_prev
        elif buff_scaled >= R_plus:
            try:    R_next = min(filter(lambda x: x < buff_scaled, bitrates))
            except: R_next = self.R_prev
        else:
            R_next = self.R_prev
        
        # look up the quality choice from the array
        qual_next = 0
        for r in sorted(bitrates):
            if r <= R_next:
                qual_next += 1
        return max(0, qual_next - 1)

    def get_quality(self, clt_msg: ClientMessage):
        self.buffer_capacity = clt_msg.buffer_seconds_until_empty

        # estimate throughput
        if clt_msg.previous_throughput: throughput = clt_msg.previous_throughput
        else:                           throughput = 1.5
        # update the reservior 
        drain_time = (2 * min(clt_msg.quality_bitrates) / throughput)
        if not self.reservoir: self.reservoir = drain_time
        else:                  self.reservoir = (self.alpha * self.reservoir) + (1-self.alpha) * drain_time

        if self.do_quickstart:
            qual_estimate = self.map_buff_to_quality(clt_msg)
            if (1 - clt_msg.quality_bitrates[qual_estimate]/throughput) > 0.875:
                qual_choice = min(qual_estimate + 1, clt_msg.quality_levels - 1)
            else:
                qual_choice = self.qual_prev
            
            self.do_quickstart  = (self.buffer_capacity >= self.buffer_capacity_prev) 
            self.do_quickstart &= (clt_msg.quality_bitrates[qual_estimate] >= self.R_prev)

        else:
            # cases for nonstartup phase
            if self.buffer_capacity < self.reservoir:
                # When the lower_reservoir is filling, select R_min
                qual_choice = 0
                self.counts[0] += 1
            elif self.buffer_capacity > (clt_msg.buffer_max_size * 0.90):
                # when the upper_reservoir is hit, select max quality
                qual_choice = clt_msg.quality_levels - 1
                self.counts[1] += 1
            else:
                # Select a chunk size as a function of the current buffer capacaty
                self.counts[2] += 1
                qual_choice = self.map_buff_to_quality(clt_msg)
        
        self.qual_prev = qual_choice
        self.R_prev    = clt_msg.quality_bitrates[qual_choice]
        self.buffer_capacity_prev = self.buffer_capacity
  
        print_dbg('\n  '.join([f'{k} == {v}' for (k,v) in clt_msg.__dict__.items()]))
        print_dbg(f'video left {clt_msg.buffer_seconds_until_empty} s')
        print_dbg(f'bitrates: {clt_msg.quality_bitrates} kB')
        print_dbg(f'chose quality {qual_choice}')
        # print_dbg(f'under: {self.counts[0]/sum(self.counts)}')
        # print_dbg(f'over:  {self.counts[1]/sum(self.counts)}')
        # print_dbg(f'mid :  {self.counts[2]/sum(self.counts)}')
        print_dbg('')

        # plotting
        self.quals.append(qual_choice)
        if len(clt_msg.upcoming_quality_bitrates) == 0:
            from matplotlib import pyplot as plt 
            plt.subplot(1,2,1)
            plt.plot(self.quals)
            plt.title('quality over time')
            plt.xlabel('chunk number')
            plt.ylabel('bitrate')

            plt.subplot(1,2,2)
            plt.hist(self.quals)
            plt.title('quality distribution')
            plt.xlabel('chunk bitrate')
            plt.ylabel('frequency')

            plt.tight_layout()
            plt.savefig('BBA_2_qualitites.png')

        return qual_choice



bba_2 = BBA_2()
print_dbg(bba_2)

def student_entrypoint(client_message: ClientMessage):
    """
    Your mission, if you choose to accept it, is to build an algorithm for chunk bitrate selection that provides
    the best possible experience for users streaming from your service.

    Construct an algorithm below that selects a quality for a new chunk given the parameters in ClientMessage. Feel
    free to create any helper function, variables, or classes as you wish.

    Simulation does ~NOT~ run in real time. The code you write can be as slow and complicated as you wish without
    penalizing your results. Focus on picking good qualities!

    Also remember the config files are built for one particular client. You can (and should!) adjust the QoE metrics to
    see how it impacts the final user score. How do algorithms work with a client that really hates rebuffering? What
    about when the client doesn't care about variation? For what QoE coefficients does your algorithm work best, and
    for what coefficients does it fail?

    Args:
      client_message : ClientMessage holding the parameters for this chunk and current client state.

    :return: float Your quality choice. Must be one in the range [0 ... quality_levels - 1] inclusive.
    """

    global bba_2

    quality = bba_2.get_quality(client_message)

    assert (0 <= quality) and (quality < client_message.quality_levels)
    return quality
