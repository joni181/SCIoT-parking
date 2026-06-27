;; Parking domain (skeleton) -- Intelligent Supermarket Parking, Group 04.
;;
;; This is a starting template, not a solved domain. Problem *instances* are
;; generated at runtime by parking/problem_generation against these predicates
;; and actions. Fill in / adjust as the planning model firms up (TODOs below).

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
    ;; TODO: predicates for "assigned", duration buckets, walking distance, ...
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

  ;; TODO: cost/metric model (walking distance, expected-duration ordering) so
  ;;       the plan minimizes customer walk + retrieval latency, per the goal.
)
