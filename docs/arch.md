Module 1 | HANDLED BY TEAM 1
    3 - 4 cpp files
    
    Agent 1 just for module 1
        take the comments, owner, prs
        update in the central database

Module 2 | HANDLED BY TEAM 2
    some other cpp files

    Agent 2 just for module 2
        take the comments, owner, prs
        update in the central database

Agent 1 and 2 may utilize different tools to get all the details

Final Agent | Generate Dashboard
    Generate dashboard - role based (different for manager -> non technical, different for tl -> more technical)

UNIT HEAD:
Display Code Quality in form of Bar Graph, it should also show number of people in the team
Punctuality score of team - eg, task was supposted to be done in 1 month, it took 2-3 weeks extra
Lets say there are 3 different customers, how many errors they have reported
2-3 different types of graphs

PROJECT MANAGER:
Will only have access to his team
For each module how many comments were received commit wise
How many customer issues are tagged to this commit -> if there are any customer issues then we should be able to point out which commit caused those issues

One internal databse -> unit, project, module, commit-id, author, reviwer, comments(major or minor), targetted and actual delivery time
One customer database -> project, module, error info, commit-id (from the internal database), severity, issue report time, issue resolve time