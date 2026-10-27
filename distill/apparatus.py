"""Apparatus templates: fixed cutaway drawings with named slots and flow paths.

The model only chooses a template, labels its slots and puts flows on its paths.
Every drawing, coordinate and colour stays here, so a figure cannot invent geometry.
Colours come from theme tokens in figures.css through the class names.
"""
from __future__ import annotations

import math


def wave(x1, y1, x2, y2, amplitude=7, waves=4):
    """A sine-like path between two points, for radiant heat."""
    length = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux
    steps = waves * 8
    points = []
    for step in range(steps + 1):
        t = step / steps
        offset = amplitude * math.sin(t * waves * 2 * math.pi)
        points.append(f"{x1 + ux * length * t + nx * offset:.1f} {y1 + uy * length * t + ny * offset:.1f}")
    return "M " + " L ".join(points)


def beans(cx, cy, columns, rows, spacing=15, cls="ap-bean", skew=0.0, jitter=(0, 3, 1, 4, 2)):
    """Deterministic bean ellipses with a centre crease."""
    out = []
    for row in range(rows):
        for column in range(columns - row % 2):
            x = cx + (column - columns / 2) * spacing + (row % 2) * spacing / 2 + jitter[(row + column) % 5] - 2
            y = cy + row * spacing * .72 + skew * column
            angle = (row * 37 + column * 53) % 120 - 60
            out.append(f'<g transform="translate({x:.1f} {y:.1f}) rotate({angle})"><ellipse class="{cls}" rx="6.5" ry="4.6"/>'
                       '<path class="ap-crease" d="M -4.5 0 Q 0 -1.6 4.5 0"/></g>')
    return "".join(out)


def particles(x1, x2, y1, y2, count=34, cls="ap-grounds"):
    out = []
    for index in range(count):
        x = x1 + (x2 - x1) * ((index * 0.618034) % 1)
        y = y1 + (y2 - y1) * ((index * 0.381966 + index % 3 * .11) % 1)
        r = 2.2 + (index % 4) * .7
        out.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/>')
    return "".join(out)


def _drum_drawing():
    vanes = "".join(
        f'<line class="ap-vane" x1="{330 + 104 * math.cos(a):.1f}" y1="{270 + 104 * math.sin(a):.1f}" '
        f'x2="{330 + 80 * math.cos(a):.1f}" y2="{270 + 80 * math.sin(a):.1f}"/>'
        for a in (math.radians(d) for d in (25, 145, 265)))
    flames = "".join(f'<path class="ap-flame" d="M {x} 470 C {x - 14} 452, {x - 4} 440, {x} 424 C {x + 4} 440, {x + 14} 452, {x} 470 Z"/>'
                     for x in (262, 296, 330, 364, 398))
    fan = "".join(f'<path class="ap-dark" d="M 640 60 L {640 + 18 * math.cos(math.radians(a)):.1f} {60 + 18 * math.sin(math.radians(a)):.1f} '
                  f'L {640 + 18 * math.cos(math.radians(a + 40)):.1f} {60 + 18 * math.sin(math.radians(a + 40)):.1f} Z"/>' for a in (0, 120, 240))
    return (
        # Hopper with green coffee, and its chute into the drum.
        '<path class="ap-metal" d="M 250 40 L 370 40 L 335 110 L 285 110 Z"/>'
        + beans(310, 58, 6, 3, spacing=14, cls="ap-green")
        + '<rect class="ap-metal" x="297" y="108" width="26" height="46"/>'
        # Air inlet at the back of the drum.
        '<rect class="ap-metal" x="40" y="288" width="176" height="24"/>'
        # Exhaust duct, damper, chaff cyclone, fan and stack.
        '<rect class="ap-metal" x="408" y="110" width="24" height="88"/>'
        '<rect class="ap-metal" x="408" y="110" width="196" height="24"/>'
        '<line class="ap-damper" x1="492" y1="113" x2="508" y2="131"/><circle class="ap-dark" cx="500" cy="122" r="3.5"/>'
        '<path class="ap-metal" d="M 600 92 L 680 92 L 680 172 L 652 250 L 628 250 L 600 172 Z"/>'
        '<rect class="ap-metal" x="620" y="250" width="40" height="30" rx="3"/>'
        '<circle class="ap-metal" cx="640" cy="60" r="24"/>' + fan +
        '<rect class="ap-metal" x="630" y="0" width="20" height="38"/>'
        # The rotating drum: wall, vanes, tumbling beans and a rotation cue.
        '<circle class="ap-drum" cx="330" cy="270" r="118"/>'
        + vanes + beans(330, 318, 12, 5, spacing=15, skew=-0.9) +
        '<path class="ap-rotation" d="M 262 196 A 92 92 0 0 1 398 196"/><path class="ap-rotation-head" d="M 398 196 l -11 -1 l 6 -9 Z"/>'
        # Radiant heater, such as a halogen lamp, inside the drum front.
        '<rect class="ap-lamp" x="395" y="205" width="60" height="16" rx="8"/>'
        '<path class="ap-filament" d="M 401 213 l 6 -4 l 6 8 l 6 -8 l 6 8 l 6 -8 l 6 8 l 6 -8 l 6 4"/>'
        # Burner under the drum.
        + flames + '<rect class="ap-metal" x="230" y="470" width="200" height="14" rx="3"/>'
        # Temperature probes: bean mass and drum air.
        '<line class="ap-probe" x1="490" y1="392" x2="372" y2="338"/><circle class="ap-dark" cx="372" cy="338" r="4"/>'
        '<line class="ap-probe" x1="490" y1="252" x2="398" y2="252"/><circle class="ap-dark" cx="398" cy="252" r="4"/>'
        # Drop chute and cooling tray.
        '<path class="ap-metal" d="M 430 332 L 446 322 L 566 410 L 548 420 Z"/>'
        '<rect class="ap-metal" x="520" y="410" width="240" height="40" rx="12"/>'
        + beans(640, 418, 13, 2, spacing=15)
    )


def _espresso_drawing():
    holes = "".join(f'<circle class="ap-hole" cx="{x}" cy="203" r="1.8"/>' for x in range(488, 636, 9))
    filter_holes = "".join(f'<circle class="ap-hole" cx="{x}" cy="275" r="1.6"/>' for x in range(494, 630, 9))
    coil = "M 268 236 " + " ".join(f"q 7 -12 14 0 q 7 12 14 0" for _ in range(5))
    return (
        # Water reservoir and its water.
        '<rect class="ap-glass" x="30" y="150" width="90" height="250" rx="6"/>'
        '<rect class="ap-water" x="33" y="250" width="84" height="147" rx="4"/>'
        '<path class="ap-line" d="M 117 380 L 160 370"/>'
        # Pump, with its line to the pressure gauge.
        '<circle class="ap-metal" cx="190" cy="360" r="30"/><path class="ap-dark" d="M 190 340 L 200 372 L 180 372 Z"/>'
        '<line class="ap-line" x1="190" y1="330" x2="190" y2="154"/>'
        '<circle class="ap-metal" cx="190" cy="120" r="34"/><circle class="ap-inner" cx="190" cy="120" r="26"/>'
        '<path class="ap-tick" d="M 170 134 L 175 130 M 190 98 L 190 104 M 210 134 L 205 130"/>'
        '<line class="ap-needle" x1="190" y1="120" x2="205" y2="104"/><circle class="ap-dark" cx="190" cy="120" r="3.5"/>'
        # Boiler with its heating element.
        '<rect class="ap-metal" x="250" y="120" width="180" height="140" rx="22"/>'
        '<rect class="ap-water" x="258" y="150" width="164" height="102" rx="14"/>'
        f'<path class="ap-element" d="{coil}"/>'
        '<path class="ap-line" d="M 220 350 C 240 330, 250 290, 258 252"/>'
        '<path class="ap-line" d="M 430 150 L 470 150"/>'
        # Group head, shower screen, headspace, puck, filter, portafilter and spout.
        '<rect class="ap-metal" x="470" y="110" width="180" height="88" rx="8"/>'
        '<rect class="ap-metal" x="480" y="198" width="160" height="8"/>' + holes +
        '<path class="ap-metal" d="M 474 206 L 646 206 L 640 286 L 480 286 Z"/>'
        '<rect class="ap-water" x="486" y="208" width="148" height="24"/>'
        '<rect class="ap-coffee" x="486" y="232" width="148" height="40"/>'
        + particles(490, 630, 236, 268, 40) +
        '<rect class="ap-metal" x="484" y="272" width="152" height="6"/>' + filter_holes +
        '<rect class="ap-metal" x="646" y="240" width="140" height="16" rx="7"/>'
        '<path class="ap-metal" d="M 548 286 L 572 286 L 566 312 L 554 312 Z"/>'
        # Cup with espresso.
        '<path class="ap-glass" d="M 505 372 L 615 372 L 606 446 Q 560 458 514 446 Z"/>'
        '<path class="ap-coffee" d="M 509 404 L 611 404 L 606 446 Q 560 458 514 446 Z"/>'
        '<path class="ap-glass" d="M 615 386 C 646 386, 646 426, 610 428"/>'
    )


def _pour_over_drawing():
    def x_at(y, side):
        return 300 + (y - 186) * 76 / 136 if side == "left" else 500 - (y - 186) * 76 / 136
    bed = f"M {x_at(232, 'left'):.1f} 232 L {x_at(232, 'right'):.1f} 232 L 424 322 L 376 322 Z"
    water = f"M {x_at(212, 'left'):.1f} 212 L {x_at(212, 'right'):.1f} 212 L {x_at(232, 'right'):.1f} 232 L {x_at(232, 'left'):.1f} 232 Z"
    ribs = "".join(f'<line class="ap-line" x1="{x_at(200, "left") + 14 * i:.1f}" y1="200" x2="{376 + 8 * i:.1f}" y2="318"/>' for i in (1, 5))
    return (
        # Kettle with handle and gooseneck spout.
        '<rect class="ap-metal" x="40" y="70" width="150" height="110" rx="26"/>'
        '<path class="ap-handle" d="M 46 96 C 4 96, 4 164, 46 164"/>'
        '<rect class="ap-metal" x="80" y="56" width="70" height="16" rx="6"/>'
        '<path class="ap-spout" d="M 186 150 C 236 150, 236 92, 332 90"/>'
        # Dripper cone, filter paper, slurry water, coffee bed and bloom bubbles.
        '<path class="ap-metal" d="M 286 176 L 514 176 L 434 334 L 366 334 Z"/>'
        '<path class="ap-paper" d="M 300 186 L 500 186 L 424 322 L 376 322 Z"/>' + ribs +
        f'<path class="ap-water" d="{water}"/><path class="ap-coffee" d="{bed}"/>'
        + particles(345, 455, 240, 314, 44) +
        "".join(f'<circle class="ap-bubble" cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in ((350, 226, 4), (372, 222, 3), (420, 224, 4.5), (446, 227, 3)))
        # Carafe with brewed coffee.
        + '<rect class="ap-metal" x="360" y="334" width="80" height="12" rx="3"/>'
        '<path class="ap-glass" d="M 330 380 L 470 380 L 480 470 Q 400 490 320 470 Z"/>'
        '<path class="ap-coffee" d="M 326 430 L 474 430 L 480 470 Q 400 490 320 470 Z"/>'
    )


TEMPLATES = {
    "drum_roaster": {
        "description": "A drum roaster in side cutaway: hopper, rotating drum with tumbling beans, gas burner below, an optional radiant heater "
                       "such as a halogen lamp, air inlet, exhaust duct with damper, chaff cyclone, fan, bean and air probes, cooling tray.",
        "draw": _drum_drawing,
        "slots": {
            "hopper": {"description": "Hopper holding green coffee before charge", "at": (226, 48)},
            "drum": {"description": "Rotating drum wall", "at": (196, 172), "to": (246, 188)},
            "bean_mass": {"description": "Tumbling bean mass inside the drum", "at": (238, 372), "to": (282, 342)},
            "burner": {"description": "Gas burner and flame under the drum", "at": (204, 462)},
            "radiant_element": {"description": "Radiant heater such as a halogen lamp, or a hot drum surface", "at": (478, 196), "to": (455, 210)},
            "air_inlet": {"description": "Air inlet at the back of the drum", "at": (64, 266)},
            "exhaust": {"description": "Exhaust duct leaving the drum", "at": (386, 98)},
            "damper": {"description": "Damper or airflow control in the exhaust", "at": (500, 86)},
            "cyclone": {"description": "Chaff cyclone separating chaff from exhaust air", "at": (708, 140)},
            "fan": {"description": "Exhaust fan drawing air through the drum", "at": (684, 34)},
            "bt_probe": {"description": "Bean temperature probe in the bean mass", "at": (516, 404)},
            "et_probe": {"description": "Environment (air) temperature probe", "at": (516, 252)},
            "cooling_tray": {"description": "Cooling tray where roasted beans are stirred and air-cooled", "at": (776, 398)},
        },
        "paths": {
            "flame_to_drum": {"description": "Burner heat rising to the drum", "kinds": ["conduction", "convection", "radiation"],
                              "d": ["M 282 424 Q 284 406 292 392", "M 330 422 L 330 394", "M 378 424 Q 376 406 368 392"]},
            "drum_to_beans": {"description": "Heat from the hot drum wall into beans that touch it", "kinds": ["conduction"],
                              "d": ["M 240 340 L 266 330", "M 330 392 L 330 366", "M 420 340 L 396 330"]},
            "hot_air": {"description": "Hot air drawn from the inlet through the drum and over the beans to the exhaust", "kinds": ["convection", "air"],
                        "d": ["M 50 300 L 214 300 C 262 300, 272 236, 326 230 S 396 208, 416 192"]},
            "radiant_heat": {"description": "Radiant heat from the heater or hot surfaces onto the beans", "kinds": ["radiation"],
                             "d": [wave(412, 226, 356, 302), wave(440, 226, 410, 300, waves=3)]},
            "bean_moisture": {"description": "Water vapour and gases leaving the beans", "kinds": ["gas"],
                              "d": ["M 300 318 C 300 270, 380 236, 412 200"]},
            "exhaust_path": {"description": "Exhaust air through the duct, damper, cyclone and fan; the fan sets drum pressure", "kinds": ["air", "gas", "pressure"],
                             "d": ["M 420 196 L 420 122 L 600 122 C 648 122, 664 158, 640 156 L 640 86 L 640 6"]},
            "charge": {"description": "Green coffee charged from the hopper into the drum", "kinds": ["material"], "d": ["M 310 62 L 310 182"]},
            "drop": {"description": "Roasted beans dropped into the cooling tray", "kinds": ["material"], "d": ["M 432 340 L 558 424"]},
            "cooling_air": {"description": "Air drawn up through the cooling tray", "kinds": ["air"],
                            "d": ["M 580 498 L 580 456", "M 640 498 L 640 456", "M 700 498 L 700 456"]},
        },
    },
    "espresso": {
        "description": "An espresso machine in cutaway: reservoir, pump, pressure gauge, boiler with heating element, group head, "
                       "shower screen, headspace water, coffee puck, basket filter, portafilter and cup.",
        "draw": _espresso_drawing,
        "slots": {
            "reservoir": {"description": "Water reservoir", "at": (75, 130)},
            "pump": {"description": "Pump that builds brewing pressure", "at": (236, 402)},
            "gauge": {"description": "Pressure gauge", "at": (144, 76)},
            "boiler": {"description": "Boiler or heat exchanger holding hot water", "at": (340, 100)},
            "heating_element": {"description": "Heating element in the boiler", "at": (238, 286), "to": (272, 240)},
            "group_head": {"description": "Group head delivering water to the basket", "at": (676, 120)},
            "shower_screen": {"description": "Shower screen spreading water over the puck", "at": (700, 182), "to": (640, 202)},
            "headspace": {"description": "Water above the puck", "at": (700, 214), "to": (634, 220)},
            "puck": {"description": "Compacted coffee puck", "at": (700, 300), "to": (634, 256)},
            "basket_filter": {"description": "Basket filter holes under the puck", "at": (456, 300), "to": (488, 276)},
            "portafilter": {"description": "Portafilter holding the basket", "at": (790, 218), "to": (770, 240)},
            "cup": {"description": "Cup collecting the espresso", "at": (660, 430)},
        },
        "paths": {
            "supply": {"description": "Water from the reservoir through the pump into the boiler", "kinds": ["water"],
                       "d": ["M 112 380 L 162 368", "M 214 344 C 236 326, 248 292, 256 254"]},
            "boiler_heat": {"description": "Heat from the element into the boiler water", "kinds": ["conduction", "convection"],
                            "d": ["M 296 236 L 296 182", "M 340 236 L 340 170", "M 384 236 L 384 182"]},
            "to_group": {"description": "Hot water from the boiler to the group head", "kinds": ["water"], "d": ["M 430 150 L 520 150 L 560 192"]},
            "shower": {"description": "Water spreading from the shower screen onto the puck", "kinds": ["water"],
                       "d": [f"M {x} 206 L {x} 230" for x in (504, 540, 580, 616)]},
            "pressure_on_puck": {"description": "Brewing pressure pressing water into the puck", "kinds": ["pressure"],
                                 "d": ["M 462 150 L 462 232", "M 658 150 L 658 232"]},
            "percolation": {"description": "Water flowing down through the coffee bed", "kinds": ["water"],
                            "d": [f"M {x} 236 L {x} 284" for x in (500, 526, 592, 618)]},
            "channel": {"description": "A channel: a fast path where water bypasses most of the coffee", "kinds": ["water"],
                        "d": ["M 552 234 L 566 246 L 556 258 L 568 270 L 560 284"]},
            "dissolved_solids": {"description": "Dissolved coffee solids carried out of the puck", "kinds": ["material"],
                                 "d": ["M 600 266 C 598 292, 576 300, 566 314"]},
            "to_cup": {"description": "Espresso flowing from the spout into the cup", "kinds": ["water"], "d": ["M 560 314 L 560 392"]},
        },
    },
    "pour_over": {
        "description": "A pour-over in cutaway: kettle, water stream, cone dripper with filter paper, slurry water, coffee bed with "
                       "bloom bubbles, drip and carafe.",
        "draw": _pour_over_drawing,
        "slots": {
            "kettle": {"description": "Kettle with a gooseneck spout", "at": (40, 46)},
            "water_stream": {"description": "Poured water stream", "at": (306, 150), "to": (356, 140)},
            "filter_paper": {"description": "Paper filter lining the cone", "at": (262, 230), "to": (312, 210)},
            "slurry": {"description": "Water standing above the coffee bed", "at": (536, 222), "to": (474, 222)},
            "coffee_bed": {"description": "Ground coffee bed", "at": (540, 286), "to": (444, 286)},
            "bloom": {"description": "Bloom: gas escaping from fresh grounds", "at": (476, 188), "to": (446, 222)},
            "cone": {"description": "Cone dripper wall and ribs", "at": (536, 168), "to": (510, 180)},
            "drip": {"description": "Brewed coffee dripping from the cone", "at": (452, 360), "to": (404, 360)},
            "carafe": {"description": "Carafe or server", "at": (500, 470)},
        },
        "paths": {
            "pour": {"description": "Water poured from the kettle onto the bed", "kinds": ["water"], "d": ["M 334 92 C 362 118, 394 160, 400 210"]},
            "percolation": {"description": "Water percolating down through the coffee bed", "kinds": ["water"],
                            "d": ["M 360 238 L 386 312", "M 400 238 L 400 316", "M 440 238 L 414 312"]},
            "bypass": {"description": "Water running down the filter wall past the bed", "kinds": ["water"],
                       "d": ["M 306 198 L 372 314", "M 494 198 L 428 314"]},
            "bloom_gas": {"description": "Carbon dioxide and other gases rising from the grounds", "kinds": ["gas"],
                          "d": ["M 360 226 C 354 208, 368 200, 360 182", "M 432 224 C 440 208, 426 198, 434 180"]},
            "extraction": {"description": "Dissolved coffee solids leaving the bed", "kinds": ["material"], "d": ["M 384 270 C 394 290, 400 306, 400 328"]},
            "drip": {"description": "Brew dripping into the carafe", "kinds": ["water"], "d": ["M 400 336 L 400 400"]},
        },
    },
}


def catalogue() -> dict:
    """What the model may choose: descriptions, slot IDs and path kinds, without drawing data."""
    return {name: {"description": item["description"],
                   "slots": {slot: value["description"] for slot, value in item["slots"].items()},
                   "paths": {path: {"description": value["description"], "kinds": value["kinds"]} for path, value in item["paths"].items()}}
            for name, item in TEMPLATES.items()}
