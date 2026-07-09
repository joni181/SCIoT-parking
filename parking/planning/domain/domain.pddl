;; Event-driven parking workflow. Sensor-confirmed transitions are planned in
;; short phases so external events trigger a fresh problem instead of allowing
;; stale multi-step plans to run ahead of the physical world.
(define (domain parking)
  (:requirements :strips :typing)

  (:types car spot buffer)

  (:predicates
    (outside ?c - car)
    (at ?c - car ?s - spot)
    (in-buffer ?c - car ?b - buffer)
    (free-spot ?s - spot)
    (free-buffer ?b - buffer)
    (arrival-requested ?c - car)
    (pickup-requested ?c - car)
    (assigned ?c - car ?s - spot)
    (entry-authorized ?c - car ?b - buffer)
    (assignment-shown ?c - car ?s - spot)
    (ready-for-pickup ?c - car ?b - buffer)
    (exit-authorized ?c - car ?b - buffer)
  )

  (:action assign
    :parameters (?c - car ?s - spot)
    :precondition (and (arrival-requested ?c) (outside ?c) (free-spot ?s))
    :effect (and (assigned ?c ?s) (not (free-spot ?s)))
  )

  (:action open-entry
    :parameters (?c - car ?b - buffer ?s - spot)
    :precondition (and (arrival-requested ?c) (outside ?c)
                       (assigned ?c ?s) (free-buffer ?b))
    :effect (and (entry-authorized ?c ?b) (not (free-buffer ?b)))
  )

  (:action show-assignment
    :parameters (?c - car ?s - spot ?b - buffer)
    :precondition (and (assigned ?c ?s) (entry-authorized ?c ?b))
    :effect (assignment-shown ?c ?s)
  )

  (:action park
    :parameters (?c - car ?b - buffer ?s - spot)
    :precondition (and (in-buffer ?c ?b) (assigned ?c ?s))
    :effect (and (at ?c ?s) (not (in-buffer ?c ?b)) (free-buffer ?b))
  )

  (:action retrieve
    :parameters (?c - car ?s - spot ?b - buffer)
    :precondition (and (at ?c ?s) (pickup-requested ?c) (free-buffer ?b))
    :effect (and (not (at ?c ?s)) (free-spot ?s)
                 (in-buffer ?c ?b) (ready-for-pickup ?c ?b)
                 (not (free-buffer ?b)))
  )

  (:action open-exit
    :parameters (?c - car ?b - buffer)
    :precondition (ready-for-pickup ?c ?b)
    :effect (exit-authorized ?c ?b)
  )
)
