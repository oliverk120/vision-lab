"""Explicit video, time-weighted, and event-level metrics; unknown is not negative."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class EvaluationConfig:
    threshold: float = 0.5
    minimum_duration: float = 0.0
    allowable_gap: float = 0.0
    tolerance: float = 0.0
    max_sample_hold: float = 1.0

    def __post_init__(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('Evaluation values must be finite')
        if not 0 <= self.threshold <= 1 or min(self.minimum_duration, self.allowable_gap, self.tolerance) < 0 or self.max_sample_hold <= 0:
            raise ValueError('Invalid evaluation configuration')


def ratio(n, d):
    return n/d if d else None


def confusion(tp=0, fp=0, tn=0, fn=0):
    precision, recall = ratio(tp,tp+fp), ratio(tp,tp+fn)
    specificity = ratio(tn,tn+fp)
    return dict(tp=tp, fp=fp, tn=tn, fn=fn, precision=precision, recall=recall,
                f1=ratio(2*tp,2*tp+fp+fn), accuracy=ratio(tp+tn,tp+tn+fp+fn),
                balanced_accuracy=None if recall is None or specificity is None else (recall+specificity)/2)


def merge(intervals, gap=0):
    output = []
    for start,end in sorted(intervals):
        if output and start <= output[-1][1]+gap:
            output[-1][1] = max(output[-1][1], end)
        else:
            output.append([start,end])
    return output


def overlap(a,b):
    return max(0, min(a[1],b[1])-max(a[0],b[0]))


def truth_at(annotations, timestamp):
    labels = {i['target'] for i in annotations['intervals']
              if i['start'] <= timestamp < i['end'] and i['target'] != 'Unknown'}
    if len(labels)>1:
        raise ValueError('Conflicting temporal labels')
    return next(iter(labels), 'Unknown')


def prediction_segments(predictions, duration, config):
    output = []
    previous = -1
    for i,p in enumerate(predictions):
        start = float(p['timestamp'])
        if not math.isfinite(start) or start < previous or start < 0 or start > duration:
            raise ValueError('Predictions must be ordered finite source timestamps')
        previous = start
        end = min(duration, start+config.max_sample_hold,
                  float(predictions[i+1]['timestamp']) if i+1<len(predictions) else duration)
        score = p.get('score')
        if score is not None and (not math.isfinite(float(score)) or not 0<=float(score)<=1):
            raise ValueError('Scores must be probabilities in [0,1], or null')
        positive = bool(p['detected']) if score is None else float(score)>=config.threshold
        if end > start:
            output.append((start,end,positive))
    return output


def evaluate(predictions, annotations, duration, config):
    segments = prediction_segments(predictions, duration, config)
    events = [i for i in merge([(a,b) for a,b,p in segments if p], config.allowable_gap)
              if i[1]-i[0] >= config.minimum_duration]
    # Video positive iff at least one grouped event survives minimum duration.
    actual = annotations['motion']
    predicted = bool(events)
    video = confusion(tp=int(actual=='Yes' and predicted), fp=int(actual=='No' and predicted),
                      tn=int(actual=='No' and not predicted), fn=int(actual=='Yes' and not predicted))
    video.update(actual=actual, predicted=predicted, excluded=int(actual=='Unknown'))
    positives = merge([(i['start'],i['end']) for i in annotations['intervals'] if i['target']=='Yes'])
    negatives = merge([(i['start'],i['end']) for i in annotations['intervals'] if i['target']=='No'])
    if any(overlap(a,b) for a in positives for b in negatives):
        raise ValueError('Conflicting temporal labels')
    weights = dict(tp=0.,fp=0.,tn=0.,fn=0.)
    for a,b,p in segments:
        # Time metrics use raw thresholded sample holds, not grouped events.
        for intervals, yes_key, no_key in ((positives,'tp','fn'),(negatives,'fp','tn')):
            weights[yes_key if p else no_key] += sum(overlap((a,b),j) for j in intervals)
    matched = []
    used = set()
    latencies = []
    for truth in positives:
        candidates = [(overlap(event,truth), -abs(event[0]-truth[0]), idx)
                      for idx,event in enumerate(events) if idx not in used
                      and event[1] > truth[0]-config.tolerance and event[0] < truth[1]+config.tolerance]
        if candidates:
            _,_,idx = max(candidates)
            used.add(idx)
            latency = max(0,events[idx][0]-truth[0])
            latencies.append(latency)
            matched.append(dict(truth=truth, event=events[idx], latency=latency))
    false_events = [e for idx,e in enumerate(events) if idx not in used and any(overlap(e,n)>0 for n in negatives)]
    ignored_events = [e for idx,e in enumerate(events) if idx not in used and e not in false_events]
    negative_seconds = sum(b-a for a,b in negatives)
    labeled_seconds = sum(b-a for a,b in positives)+negative_seconds
    return dict(video=video, temporal=confusion(**weights),
                labeled_seconds=labeled_seconds, evaluated_seconds=sum(weights.values()),
                uncovered_labeled_seconds=max(0,labeled_seconds-sum(weights.values())),
                events=dict(predicted=events, truth=positives, matched=matched,
                            detected=len(matched), missed=len(positives)-len(matched),
                            false_alarms=len(false_events), false_intervals=false_events,
                            ignored_unmatched=ignored_events,
                            precision=ratio(len(matched),len(matched)+len(false_events)),
                            recall=ratio(len(matched),len(positives)),
                            false_alarms_per_minute=ratio(len(false_events),negative_seconds/60),
                            latency_mean_seconds=ratio(sum(latencies),len(latencies))))
