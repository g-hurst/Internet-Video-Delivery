from typing import List
from itertools import product

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


# Your helper functions, variables, classes here. You may also write initialization routines to be called
# when this script is first imported and anything else you wish.
DBG = False
def print_dbg(*args):
    global DBG
    if DBG: print(*args)

class Robust_MPC():
    def __init__(self):
        self.qual_prev = 0
        self.throughput = None
        self.througput_prev = 0
        self.throughput_error = 0

        self.lookback_window  = 5
        self.lookahead_window = 5
        self.throughput_hist  = []

        self.plot_num = 1
        self.quals = []
        self.counts = [0,0,0]

    def __str__(self):
        msg = f'bb2:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        return msg

    # calculate the harmonic mean from the past self.lookback_window throughput values
    def get_mean_throughput(self, tp_prev:int):
        self.throughput_hist.append(tp_prev)
        if len(self.throughput_hist) > self.lookback_window:
            self.throughput_hist = self.throughput_hist[-self.lookback_window:]
        
        avg = 0
        for tp in self.throughput_hist:
            avg += 1 / tp
        return len(self.throughput_hist) / avg

    # transform bitrate options to times based on the estimated throughput
    def get_time_from_bitrates(self, bitrates_curr, bitrates_next):
        times = [bitrates_curr,]
        for i in range(self.lookahead_window - 1):
            try: times.append( [(r/self.throughput) for r in bitrates_next[i]] )
            except: break
        return times

    def calc_MPC(self, clt_msg:ClientMessage):
        # caclulates differences in an array of qualitites
        # used for varience metric
        def calc_diffs(quals):
            for i in range(len(quals)):
                if i == 0: yield abs(self.qual_prev - quals[i])
                else:      yield abs(quals[i] - quals[i-1])


        qual_max   = 0
        qoe_max    = -1000 # arbitrary large negitive (REALLY bad if QOE is this low)
        times      = self.get_time_from_bitrates(clt_msg.quality_bitrates, clt_msg.upcoming_quality_bitrates)
        qual_paths = list(product( *[list(range(len(t))) for t in times] )) # all possible paths within given lookahead
        for path in qual_paths:
            # calculate metrics that factor into QOE
            quality     = sum(path)
            rebuff_time = max(0, sum([times[i][j] for (i, j) in enumerate(path)]) - self.buffer_capacity)
            rebuff_time = rebuff_time / (1 + self.throughput_error)
            variation   = sum(calc_diffs(path))

            # calculate the QOE of the given path based on config metrics
            qoe_temp    = clt_msg.quality_coefficient     * quality
            qoe_temp   -= clt_msg.rebuffering_coefficient * rebuff_time
            qoe_temp   -= clt_msg.variation_coefficient   * variation
            
            # select bitrate that yields the hightst QOE
            if qoe_temp > qoe_max:
                qoe_max  = qoe_temp
                qual_max = path[0]
        
        return qual_max

    def get_quality(self, clt_msg: ClientMessage):
        self.buffer_capacity = clt_msg.buffer_seconds_until_empty
                
        # perform throughput prediction
        self.througput_prev= self.throughput
        if clt_msg.previous_throughput: 
            self.throughput       = self.get_mean_throughput(clt_msg.previous_throughput)
            self.throughput_error = abs(self.througput_prev- self.throughput) / self.througput_prev
        else:                           
            self.throughput      = 1.5
            self.througput_error = 0
        # calculate bitrate (R) and (startup delay (T_s) in init phase)
        qual_choice = self.calc_MPC(clt_msg)
        
        self.qual_prev = qual_choice
  
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

            plt.subplot(1,2, 2)
            plt.hist(self.quals)
            plt.title('quality distribution')
            plt.xlabel('chunk bitrate')
            plt.ylabel('frequency')

            plt.tight_layout()
            plt.savefig('Robust_MPC_qualitites.png')
            plt.clf()

        return qual_choice



robust_MPC = Robust_MPC()
print_dbg(robust_MPC)

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

    global robust_MPC

    quality = robust_MPC.get_quality(client_message)

    assert (0 <= quality) and (quality < client_message.quality_levels)
    return quality
