# Set up authorization for Rosterly

Rosterly is a five-person startup building shift scheduling for clinics. Our
first service, `schedules-api`, needs real authorization before our pilot
customers start paying next quarter. Background is in `/workspace/README.md`,
the rules product signed off are in `/workspace/docs/permissions.md`, and what
is coming next is in `/workspace/docs/roadmap.md` (a React dashboard, a second
service, and SOC 2 next year). We have no platform or SRE engineer.

We've decided to use Cerbos, but nobody here has used it. We don't want to
over-build for one service, and we don't want to redo everything in six months
either. Write `/workspace/DESIGN.md` for the team that:

1. recommends how we should set up Cerbos now — what runs where, and how our
   policies get written, tested and delivered,
2. explains why, given our roadmap,
3. says what we can leave until later, and
4. lists the concrete next steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
