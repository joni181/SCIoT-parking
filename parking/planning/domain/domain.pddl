;; Parking domain -- Intelligent Supermarket Parking, Group 04.
;; Runtime problem instances select concrete assignment goals based on expected
;; stay duration; forward search determines the valid move sequence.

(define (domain parking)
  (:requirements :strips :typing)

  (:types
    car
    spot        ; a numbered parking spot
    buffer      ; an entrance buffer/drop-off slot
  )

  (:predicates
    (at ?c - car ?s - spot)        ; car ?c is parked in spot ?s
    (in-buffer ?c - car ?b - buffer)
    (free-spot ?s - spot)
    (free-buffer ?b - buffer)
  )

  ;; Drop a car off the buffer into a free spot.
  (:action park
    :parameters (?c - car ?b - buffer ?s - spot)
    :precondition (and (in-buffer ?c ?b) (free-spot ?s))
    :effect (and (not (in-buffer ?c ?b)) (free-buffer ?b)
                 (at ?c ?s) (not (free-spot ?s)))
  )

  ;; Retrieve a parked car back to a free buffer for pickup.
  (:action retrieve
    :parameters (?c - car ?s - spot ?b - buffer)
    :precondition (and (at ?c ?s) (free-buffer ?b))
    :effect (and (not (at ?c ?s)) (free-spot ?s)
                 (in-buffer ?c ?b) (not (free-buffer ?b)))
  )
)
